"""Finance Q&A Agent: general financial education grounded in the RAG KB."""

from __future__ import annotations

from langchain_core.messages import BaseMessage

from src.agents.base_agent import AgentResponse, BaseAgent
from src.rag.retriever import KnowledgeRetriever


class FinanceQAAgent(BaseAgent):
    name = "finance_qa"
    description = "Answers general financial education questions using the knowledge base."

    def __init__(self, llm=None, retriever: KnowledgeRetriever | None = None):
        super().__init__(llm)
        self.retriever = retriever or KnowledgeRetriever()

    @property
    def system_prompt(self) -> str:
        return (
            "You are a friendly financial educator for complete beginners. "
            "Answer using the provided knowledge-base context when relevant, citing it as "
            "[1], [2], etc. Use simple analogies, short paragraphs, and define every term "
            "you introduce. If the context does not cover the question, answer from "
            "well-established financial principles and say the knowledge base did not cover it."
        )

    def respond(self, query: str, history: list[BaseMessage] | None = None, **kwargs) -> AgentResponse:
        chunks = self.retriever.search(query)
        context = self.retriever.format_context(chunks)
        text = self._invoke(self._build_messages(query, history, context))
        return self._finalize(text, citations=self.retriever.citations(chunks))
