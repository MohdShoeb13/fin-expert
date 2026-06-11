"""Shared fixtures: fake LLMs, fake market data, in-memory RAG store."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.data.market_data import HistoryPoint, Quote


class FakeLLM(FakeListChatModel):
    """Deterministic chat model for agent tests."""

    def __init__(self, responses: list[str] | None = None):
        super().__init__(responses=responses or ["This is an educational answer."])


@pytest.fixture
def fake_llm():
    return FakeLLM()


class FakeMarketService:
    """In-memory market data source with controllable failures."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.prices = {"AAPL": 200.0, "VTI": 300.0, "BND": 70.0, "SPY": 600.0}

    def get_quote(self, symbol: str) -> Quote:
        from src.data.market_data import MarketDataUnavailable
        from src.utils.validators import normalize_ticker

        symbol = normalize_ticker(symbol)  # raise ValueError like the real service
        if self.fail or symbol not in self.prices:
            raise MarketDataUnavailable(f"no quote for {symbol}")
        price = self.prices[symbol]
        return Quote(
            symbol=symbol,
            price=price,
            change=1.0,
            change_percent=0.5,
            name=f"{symbol} Test Co",
            previous_close=price - 1.0,
            pe_ratio=20.0,
            fifty_two_week_high=price * 1.2,
            fifty_two_week_low=price * 0.8,
            provider="fake",
        )

    def get_history(self, symbol: str, period: str = "6mo") -> list[HistoryPoint]:
        if self.fail:
            from src.data.market_data import MarketDataUnavailable

            raise MarketDataUnavailable("history down")
        return [
            HistoryPoint(date=f"2026-0{m}-01", close=100.0 + m) for m in range(1, 6)
        ]

    def get_news(self, symbol: str, limit: int = 8) -> list[dict]:
        if self.fail:
            return []
        return [
            {"title": f"{symbol} announces results", "publisher": "TestWire", "link": "", "published": "", "summary": ""}
        ][:limit]


@pytest.fixture
def fake_market():
    return FakeMarketService()


@pytest.fixture
def failing_market():
    return FakeMarketService(fail=True)


@pytest.fixture
def patched_market(monkeypatch, fake_market):
    """Patch the global market service used by portfolio analytics."""
    import src.data.market_data as md

    monkeypatch.setattr(md, "_service", fake_market)
    return fake_market


class FakeRetriever:
    """Stands in for KnowledgeRetriever without loading FAISS."""

    def search(self, query, top_k=None, category=None):
        from src.rag.retriever import RetrievedChunk

        return [
            RetrievedChunk(
                content="Compound interest is earning returns on returns.",
                title="Compound Interest",
                category=category or "basics",
                source="Test KB",
                score=0.9,
            )
        ]

    format_context = staticmethod(lambda chunks: "\n".join(c.content for c in chunks))

    @staticmethod
    def citations(chunks):
        return [{"title": c.title, "source": c.source, "category": c.category, "score": c.score} for c in chunks]


@pytest.fixture
def fake_retriever():
    return FakeRetriever()
