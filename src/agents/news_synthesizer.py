"""News Synthesizer Agent: fetches and contextualizes financial news."""

from __future__ import annotations

import json

from langchain_core.messages import BaseMessage

from src.agents.base_agent import AgentResponse, BaseAgent
from src.agents.market_analysis import extract_symbols
from src.data.market_data import get_market_data_service

# Broad-market proxies used when no specific company is mentioned.
_MARKET_PROXIES = ["SPY", "QQQ"]


class NewsSynthesizerAgent(BaseAgent):
    name = "news_synthesizer"
    description = "Summarizes and contextualizes recent financial news."

    def __init__(self, llm=None, market_service=None):
        super().__init__(llm)
        self._market = market_service

    @property
    def market(self):
        if self._market is None:
            self._market = get_market_data_service()
        return self._market

    @property
    def system_prompt(self) -> str:
        return (
            "You are a financial news educator. You receive recent headlines as JSON. "
            "Synthesize them into a short briefing for a beginner: group related stories, "
            "explain why each theme matters in plain language, and connect them to "
            "concepts the user may be learning (earnings, interest rates, etc.). "
            "Attribute claims to their publisher. Do not speculate beyond the headlines, "
            "and never turn news into a buy/sell recommendation."
        )

    def respond(self, query: str, history: list[BaseMessage] | None = None, **kwargs) -> AgentResponse:
        symbols = kwargs.get("symbols") or extract_symbols(query) or _MARKET_PROXIES
        articles: list[dict] = []
        for symbol in symbols[:3]:
            for item in self.market.get_news(symbol, limit=5):
                item["related_symbol"] = symbol
                articles.append(item)

        if not articles:
            return self._finalize(
                "I couldn't retrieve any recent news right now — the news feed may be "
                "temporarily unavailable. Please try again in a few minutes."
            )

        context = f"Recent headlines:\n{json.dumps(articles, indent=2)}"
        text = self._invoke(self._build_messages(query, history, context))
        return self._finalize(text, data={"articles": articles})
