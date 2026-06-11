"""Tax Education Agent: explains tax concepts and account types via RAG."""

from __future__ import annotations

from langchain_core.messages import BaseMessage

from src.agents.base_agent import AgentResponse, BaseAgent
from src.rag.retriever import KnowledgeRetriever


class TaxEducationAgent(BaseAgent):
    name = "tax_education"
    description = "Explains tax concepts, account types, and tax-efficient investing."

    def __init__(self, llm=None, retriever: KnowledgeRetriever | None = None):
        super().__init__(llm)
        self.retriever = retriever or KnowledgeRetriever()

    @property
    def system_prompt(self) -> str:
        return (
            "You are a tax education specialist for individual investors. Explain tax "
            "concepts (capital gains, account types, tax-loss harvesting, brackets) using "
            "the provided knowledge-base context, citing it as [1], [2], etc. Use concrete "
            "numeric examples. You teach how the rules work in general — you do NOT "
            "prepare taxes or give personalized tax advice, and you should remind users "
            "to consult a tax professional for their specific situation. Note that tax "
            "thresholds change yearly, so figures are approximate."
        )

    def respond(self, query: str, history: list[BaseMessage] | None = None, **kwargs) -> AgentResponse:
        # Prefer tax articles, but fall back to the whole KB (retirement accounts
        # overlap heavily with tax questions).
        chunks = self.retriever.search(query, category="tax")
        if len(chunks) < 2:
            chunks = self.retriever.search(query)
        context = self.retriever.format_context(chunks)
        text = self._invoke(self._build_messages(query, history, context))
        return self._finalize(text, citations=self.retriever.citations(chunks))
