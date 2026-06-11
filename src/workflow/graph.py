"""LangGraph StateGraph wiring: router -> specialized agent -> response.

Conversation memory is persisted per session via a SQLite checkpointer, so
multi-turn context survives across requests (and server restarts).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from src.core.config import PROJECT_ROOT, get_config
from src.core.logging import get_logger
from src.workflow.router import ROUTES, classify
from src.workflow.state import AssistantState

logger = get_logger(__name__)

FALLBACK_MESSAGE = (
    "I ran into a problem answering that. Please try rephrasing your question, "
    "or try again in a moment.\n\n📘 *This is educational content, not financial advice. "
    "Consult a licensed financial advisor before making investment decisions.*"
)


def route_node(state: AssistantState) -> dict:
    query = _last_user_message(state)
    route = classify(query) if query else "finance_qa"
    logger.info("Routed query to %s", route)
    return {"route": route}


def _last_user_message(state: AssistantState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def make_agent_node(agent_name: str):
    def agent_node(state: AssistantState) -> dict:
        from src.agents.registry import get_agent

        query = _last_user_message(state)
        history = state.get("messages", [])[:-1]
        max_history = get_config().get("workflow.max_history_messages", 20)
        history = history[-max_history:]

        kwargs = {}
        if agent_name == "portfolio_analysis":
            kwargs["holdings"] = state.get("holdings") or []
        if agent_name == "goal_planning":
            kwargs.update(state.get("goal_params") or {})

        try:
            response = get_agent(agent_name).respond(query, history=history, **kwargs)
            return {
                "messages": [AIMessage(content=response.content)],
                "agent_response": response.to_dict(),
            }
        except Exception as exc:  # noqa: BLE001 - graded fallback path
            logger.exception("Agent %s failed", agent_name)
            return {
                "messages": [AIMessage(content=FALLBACK_MESSAGE)],
                "agent_response": {
                    "content": FALLBACK_MESSAGE,
                    "agent": agent_name,
                    "citations": [],
                    "data": {},
                },
                "error": str(exc),
            }

    agent_node.__name__ = f"{agent_name}_node"
    return agent_node


def build_graph(checkpointer=None):
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(AssistantState)
    graph.add_node("router", route_node)
    for route in ROUTES:
        graph.add_node(route, make_agent_node(route))

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", lambda s: s["route"], {r: r for r in ROUTES})
    for route in ROUTES:
        graph.add_edge(route, END)

    if checkpointer is None:
        checkpointer = _sqlite_checkpointer()
    return graph.compile(checkpointer=checkpointer)


def _sqlite_checkpointer():
    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = PROJECT_ROOT / get_config().get(
        "workflow.checkpoint_db", ".checkpoints/conversations.sqlite"
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


_compiled = None


def get_workflow():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


def _build_state(message: str, holdings: list[dict] | None, goal_params: dict | None) -> dict:
    state: dict = {"messages": [HumanMessage(content=message)]}
    if holdings:
        state["holdings"] = holdings
    if goal_params:
        state["goal_params"] = goal_params
    return state


_FALLBACK_RESPONSE = {
    "content": FALLBACK_MESSAGE,
    "agent": "unknown",
    "citations": [],
    "data": {},
}


def run_turn(
    session_id: str,
    message: str,
    holdings: list[dict] | None = None,
    goal_params: dict | None = None,
) -> dict:
    """Run one conversational turn for a session; returns AgentResponse dict."""
    workflow = get_workflow()
    state = _build_state(message, holdings, goal_params)

    result = workflow.invoke(state, config={"configurable": {"thread_id": session_id}})
    response = result.get("agent_response") or dict(_FALLBACK_RESPONSE)
    response["route"] = result.get("route", "")
    return response


def stream_turn(
    session_id: str,
    message: str,
    holdings: list[dict] | None = None,
    goal_params: dict | None = None,
):
    """Run one turn, yielding events as the LLM generates tokens.

    Events:
        {"type": "route", "route": str}      router decided which agent handles it
        {"type": "token", "text": str}       one LLM token from the agent node
        {"type": "done", "response": dict}   final AgentResponse (disclaimer, citations)
        {"type": "error", "detail": str}     unrecoverable failure (still followed by done)
    """
    workflow = get_workflow()
    state = _build_state(message, holdings, goal_params)

    route = ""
    response: dict | None = None
    try:
        for mode, payload in workflow.stream(
            state,
            config={"configurable": {"thread_id": session_id}},
            stream_mode=["updates", "messages"],
        ):
            if mode == "updates":
                for node, update in (payload or {}).items():
                    if not isinstance(update, dict):
                        continue
                    if node == "router" and update.get("route"):
                        route = update["route"]
                        yield {"type": "route", "route": route}
                    elif update.get("agent_response"):
                        response = update["agent_response"]
            elif mode == "messages":
                chunk, metadata = payload
                if metadata.get("langgraph_node") == "router":
                    continue  # classification tokens are not part of the answer
                if not isinstance(chunk, AIMessageChunk):
                    continue  # full AIMessages from state updates would duplicate the text
                text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                if text:
                    yield {"type": "token", "text": text}
    except Exception as exc:  # noqa: BLE001 - stream must always terminate cleanly
        logger.exception("Streaming turn failed")
        yield {"type": "error", "detail": str(exc)}

    final = response or dict(_FALLBACK_RESPONSE)
    final["route"] = route
    yield {"type": "done", "response": final}
