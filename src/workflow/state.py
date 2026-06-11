"""Shared LangGraph state for the multi-agent workflow."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AssistantState(TypedDict, total=False):
    # Conversation history; add_messages appends rather than replaces.
    messages: Annotated[list[BaseMessage], add_messages]
    # Which agent the router selected for this turn.
    route: str
    # Structured inputs passed by the UI (not parsed from text).
    holdings: list[dict]
    goal_params: dict
    # Outputs of the selected agent for this turn.
    agent_response: dict  # AgentResponse.to_dict()
    error: str
