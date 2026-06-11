"""Base class shared by all six specialized agents.

Each agent owns: an LLM (resolved per-agent from the multi-provider registry),
a system prompt, and a `respond()` implementation. Responses always carry the
educational disclaimer and any source citations / structured data the UI needs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.core.llm_registry import get_llm_for_agent
from src.core.logging import get_logger
from src.utils.disclaimers import with_disclaimer

logger = get_logger(__name__)

COMMON_GUARDRAILS = """
Rules you must always follow:
- You provide financial EDUCATION, never personalized financial advice.
- Never recommend buying or selling a specific security.
- Explain jargon in plain language suitable for beginners.
- When you use provided context or data, ground your answer in it and do not invent figures.
- If you are unsure or the data is unavailable, say so clearly.
"""


@dataclass
class AgentResponse:
    content: str
    agent: str
    citations: list[dict] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "agent": self.agent,
            "citations": self.citations,
            "data": self.data,
        }


class BaseAgent(ABC):
    """name must match a key under llm.agents in config.yaml."""

    name: str = "base"
    description: str = ""

    def __init__(self, llm=None):
        self._llm = llm

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm_for_agent(self.name)
        return self._llm

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def respond(self, query: str, history: list[BaseMessage] | None = None, **kwargs) -> AgentResponse: ...

    # ------------------------------------------------------------- helpers

    def _build_messages(
        self,
        query: str,
        history: list[BaseMessage] | None = None,
        context: str | None = None,
    ) -> list[BaseMessage]:
        messages: list[BaseMessage] = [
            SystemMessage(content=f"{self.system_prompt}\n{COMMON_GUARDRAILS}")
        ]
        if history:
            messages.extend(history)
        user_content = query
        if context:
            user_content = f"Context:\n{context}\n\nUser question: {query}"
        messages.append(HumanMessage(content=user_content))
        return messages

    def _invoke(self, messages: list[BaseMessage]) -> str:
        result: AIMessage = self.llm.invoke(messages)
        return result.content if isinstance(result.content, str) else str(result.content)

    def _finalize(self, text: str, citations: list[dict] | None = None, data: dict | None = None) -> AgentResponse:
        return AgentResponse(
            content=with_disclaimer(text),
            agent=self.name,
            citations=citations or [],
            data=data or {},
        )
