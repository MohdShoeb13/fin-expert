"""Market Analysis Agent: real-time quotes and trend insights."""

from __future__ import annotations

import json
import re

from langchain_core.messages import BaseMessage

from src.agents.base_agent import AgentResponse, BaseAgent
from src.data.market_data import MarketDataUnavailable, get_market_data_service

# Words that look like tickers but aren't.
_STOPWORDS = {
    "I", "A", "THE", "AND", "OR", "FOR", "TO", "OF", "IN", "ON", "IS", "ARE",
    "HOW", "WHAT", "WHY", "WHO", "DO", "DOES", "MY", "ME", "VS", "ETF", "USD",
    "CEO", "IPO", "AI", "US", "UP", "NOW", "BUY", "SELL", "GOOD", "BAD", "PE",
}

# Common company-name -> ticker mapping for beginner-friendly queries.
_NAME_MAP = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "tesla": "TSLA", "nvidia": "NVDA", "meta": "META",
    "netflix": "NFLX", "s&p 500": "^GSPC", "s&p": "^GSPC", "nasdaq": "^IXIC",
    "dow": "^DJI", "dow jones": "^DJI", "bitcoin": "BTC-USD",
}


def extract_symbols(query: str, max_symbols: int = 3) -> list[str]:
    """Pull likely ticker symbols / well-known company names from a query."""
    found: list[str] = []
    remaining = query
    for name, ticker in _NAME_MAP.items():
        if name in remaining.lower():
            if ticker not in found:
                found.append(ticker)
            remaining = re.sub(re.escape(name), " ", remaining, flags=re.I)
    for token in re.findall(r"\b[A-Z]{1,5}\b", remaining):
        if token not in _STOPWORDS and token not in found:
            found.append(token)
    return found[:max_symbols]


class MarketAnalysisAgent(BaseAgent):
    name = "market_analysis"
    description = "Provides real-time stock quotes, trends, and market insights."

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
            "You are a market analysis educator. You receive live market data as JSON "
            "(price, daily change, valuation metrics, 52-week range, recent trend). "
            "Summarize what the data shows in beginner-friendly terms: current price and "
            "move, where it sits in its 52-week range, and what metrics like P/E mean. "
            "Note when data is cached/stale. Describe and educate — never predict prices "
            "or tell the user to buy or sell."
        )

    def respond(self, query: str, history: list[BaseMessage] | None = None, **kwargs) -> AgentResponse:
        symbols = kwargs.get("symbols") or extract_symbols(query)
        if not symbols:
            return self._finalize(
                "Which stock or index would you like to look at? Give me a ticker symbol "
                "(like AAPL or VTI) or a company name, and I'll pull the latest data."
            )

        quotes, trends, errors = [], {}, []
        for symbol in symbols:
            try:
                quotes.append(self.market.get_quote(symbol).to_dict())
                history_points = self.market.get_history(symbol, "3mo")
                if history_points:
                    first, last = history_points[0].close, history_points[-1].close
                    trends[symbol] = {
                        "3mo_change_percent": round((last - first) / first * 100, 2),
                        "3mo_low": min(p.close for p in history_points),
                        "3mo_high": max(p.close for p in history_points),
                    }
            except (MarketDataUnavailable, ValueError) as exc:
                errors.append(f"{symbol}: {exc}")

        if not quotes:
            return self._finalize(
                "I couldn't fetch market data right now — the data providers may be "
                f"temporarily unavailable. Details: {'; '.join(errors)}. Please try again shortly."
            )

        context = json.dumps({"quotes": quotes, "trends_3mo": trends, "errors": errors}, indent=2)
        text = self._invoke(self._build_messages(query, history, f"Live market data:\n{context}"))
        return self._finalize(text, data={"quotes": quotes, "trends": trends})
