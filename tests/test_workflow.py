"""Integration tests for the LangGraph workflow (mocked router + agents)."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.base_agent import AgentResponse
from src.workflow import graph as graph_module
from src.workflow.graph import FALLBACK_MESSAGE, build_graph, run_turn
from src.workflow.router import ROUTES


class StubAgent:
    name = "finance_qa"

    def respond(self, query, history=None, **kwargs):
        return AgentResponse(
            content=f"Educational answer to: {query}",
            agent=self.name,
            citations=[{"title": "T", "source": "S"}],
        )


class ExplodingAgent:
    name = "finance_qa"

    def respond(self, query, history=None, **kwargs):
        raise RuntimeError("LLM provider exploded")


@pytest.fixture
def stub_routing(monkeypatch):
    """Route everything to finance_qa without an LLM."""
    monkeypatch.setattr(graph_module, "classify", lambda q: "finance_qa")


def patch_agent(monkeypatch, agent):
    import src.agents.registry as registry

    monkeypatch.setattr(registry, "get_agent", lambda name: agent)


def test_graph_compiles_with_all_routes():
    compiled = build_graph(checkpointer=False)
    node_names = set(compiled.get_graph().nodes)
    assert set(ROUTES) <= node_names
    assert "router" in node_names


def test_turn_flows_router_to_agent(monkeypatch, stub_routing):
    patch_agent(monkeypatch, StubAgent())
    workflow = build_graph(checkpointer=False)

    result = workflow.invoke({"messages": [HumanMessage(content="What is a bond?")]})
    assert result["route"] == "finance_qa"
    assert "Educational answer to: What is a bond?" in result["agent_response"]["content"]
    assert isinstance(result["messages"][-1], AIMessage)


def test_agent_failure_returns_fallback(monkeypatch, stub_routing):
    patch_agent(monkeypatch, ExplodingAgent())
    workflow = build_graph(checkpointer=False)

    result = workflow.invoke({"messages": [HumanMessage(content="boom")]})
    assert result["agent_response"]["content"] == FALLBACK_MESSAGE
    assert "exploded" in result["error"]


def test_run_turn_returns_response_with_route(monkeypatch, stub_routing):
    patch_agent(monkeypatch, StubAgent())
    monkeypatch.setattr(graph_module, "get_workflow", lambda: build_graph(checkpointer=False))

    response = run_turn("session-1", "What is a bond?")
    assert response["route"] == "finance_qa"
    assert response["agent"] == "finance_qa"
    assert response["citations"]


def test_session_memory_preserved_across_turns(monkeypatch, stub_routing, tmp_path):
    from langgraph.checkpoint.sqlite import SqliteSaver
    import sqlite3

    seen_history_lengths = []

    class HistoryAwareAgent(StubAgent):
        def respond(self, query, history=None, **kwargs):
            seen_history_lengths.append(len(history or []))
            return super().respond(query, history=history, **kwargs)

    patch_agent(monkeypatch, HistoryAwareAgent())
    conn = sqlite3.connect(str(tmp_path / "test.sqlite"), check_same_thread=False)
    workflow = build_graph(checkpointer=SqliteSaver(conn))
    monkeypatch.setattr(graph_module, "get_workflow", lambda: workflow)

    run_turn("memory-session", "first message")
    run_turn("memory-session", "second message")
    run_turn("other-session", "unrelated message")

    # Turn 2 sees turn 1's human+AI messages; a fresh session sees nothing.
    assert seen_history_lengths[0] == 0
    assert seen_history_lengths[1] == 2
    assert seen_history_lengths[2] == 0


def test_holdings_passed_to_portfolio_agent(monkeypatch):
    captured = {}

    class CapturingAgent:
        name = "portfolio_analysis"

        def respond(self, query, history=None, **kwargs):
            captured.update(kwargs)
            return AgentResponse(content="ok", agent=self.name)

    monkeypatch.setattr(graph_module, "classify", lambda q: "portfolio_analysis")
    patch_agent(monkeypatch, CapturingAgent())
    monkeypatch.setattr(graph_module, "get_workflow", lambda: build_graph(checkpointer=False))

    holdings = [{"symbol": "VTI", "shares": 10, "asset_type": "stock_etf"}]
    run_turn("s", "analyze my portfolio", holdings=holdings)
    assert captured["holdings"] == holdings
