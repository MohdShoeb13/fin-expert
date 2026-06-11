"""Tests for the market data fallback chain (src/data/market_data.py).

Chain under test: fresh cache -> yFinance -> Alpha Vantage -> stale cache -> error.
Providers are mocked at the _fetch_* level; no network calls.
"""

import pytest

from src.data.market_data import MarketDataService, MarketDataUnavailable, Quote


def make_service() -> MarketDataService:
    svc = MarketDataService()
    svc.max_retries = 2
    svc.backoff_base = 0.0  # no sleeping in tests
    return svc


def fake_quote(symbol="AAPL", price=100.0, provider="yfinance") -> Quote:
    return Quote(symbol=symbol, price=price, change=1.0, change_percent=1.0, provider=provider)


def test_primary_provider_success_and_cached(monkeypatch):
    svc = make_service()
    calls = {"n": 0}

    def yf(symbol):
        calls["n"] += 1
        return fake_quote(symbol)

    monkeypatch.setattr(svc, "_fetch_yfinance", yf)

    q1 = svc.get_quote("AAPL")
    q2 = svc.get_quote("AAPL")  # must come from cache
    assert q1.price == 100.0
    assert q2 is q1
    assert calls["n"] == 1


def test_fallback_to_alpha_vantage(monkeypatch):
    svc = make_service()

    def yf(symbol):
        raise ConnectionError("yfinance down")

    monkeypatch.setattr(svc, "_fetch_yfinance", yf)
    monkeypatch.setattr(
        svc, "_fetch_alpha_vantage", lambda s: fake_quote(s, 99.0, "alpha_vantage")
    )

    q = svc.get_quote("AAPL")
    assert q.provider == "alpha_vantage"
    assert q.price == 99.0


def test_retries_before_giving_up(monkeypatch):
    svc = make_service()
    attempts = {"n": 0}

    def flaky(symbol):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise ConnectionError("transient")
        return fake_quote(symbol)

    monkeypatch.setattr(svc, "_fetch_yfinance", flaky)
    q = svc.get_quote("AAPL")
    assert q.price == 100.0
    assert attempts["n"] == 2


def test_stale_cache_served_when_all_providers_fail(monkeypatch):
    svc = make_service()
    monkeypatch.setattr(svc, "_fetch_yfinance", lambda s: fake_quote(s))
    svc.get_quote("AAPL")  # warm the cache

    # Expire the cache and kill both providers.
    svc.quote_cache._data["AAPL"].stored_at -= svc.quote_cache.ttl + 100

    def boom(symbol):
        raise ConnectionError("down")

    monkeypatch.setattr(svc, "_fetch_yfinance", boom)
    monkeypatch.setattr(svc, "_fetch_alpha_vantage", boom)

    q = svc.get_quote("AAPL")
    assert q.stale is True
    assert q.price == 100.0


def test_total_failure_raises(monkeypatch):
    svc = make_service()

    def boom(symbol):
        raise ConnectionError("down")

    monkeypatch.setattr(svc, "_fetch_yfinance", boom)
    monkeypatch.setattr(svc, "_fetch_alpha_vantage", boom)

    with pytest.raises(MarketDataUnavailable, match="AAPL"):
        svc.get_quote("AAPL")


def test_invalid_symbol_rejected_before_fetch():
    svc = make_service()
    with pytest.raises(ValueError, match="Invalid ticker"):
        svc.get_quote("not a ticker!!")


def test_alpha_vantage_requires_key(monkeypatch):
    svc = make_service()
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    with pytest.raises(MarketDataUnavailable, match="key"):
        svc._fetch_alpha_vantage("AAPL")


def test_quote_to_dict_carries_freshness_metadata():
    d = fake_quote().to_dict()
    assert {"symbol", "price", "provider", "as_of", "stale"} <= d.keys()
    assert d["stale"] is False


# ------------------------------------------------ provider response parsing

class FakeTicker:
    """Stands in for yfinance.Ticker with canned payloads."""

    info: dict = {}
    news_items: list = []

    def __init__(self, symbol):
        self.symbol = symbol
        self.news = self.news_items

    def history(self, period="6mo"):
        raise ConnectionError("not used in these tests")


def test_yfinance_quote_parsing(monkeypatch):
    import yfinance

    FakeTicker.info = {
        "regularMarketPrice": 150.0,
        "regularMarketPreviousClose": 148.0,
        "shortName": "Apple Inc.",
        "currency": "USD",
        "marketCap": 2_500_000_000_000,
        "trailingPE": 28.5,
        "fiftyTwoWeekHigh": 200.0,
        "fiftyTwoWeekLow": 120.0,
    }
    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)

    q = make_service()._fetch_yfinance("AAPL")
    assert q.price == 150.0
    assert q.change == pytest.approx(2.0)
    assert q.change_percent == pytest.approx(2 / 148 * 100, abs=0.001)
    assert q.name == "Apple Inc."
    assert q.pe_ratio == 28.5
    assert q.provider == "yfinance"


def test_yfinance_no_price_raises(monkeypatch):
    import yfinance

    FakeTicker.info = {"shortName": "Ghost Corp"}
    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)

    with pytest.raises(ValueError, match="no price"):
        make_service()._fetch_yfinance("GHOST")


def test_alpha_vantage_quote_parsing(monkeypatch):
    import src.data.market_data as md

    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-key")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"Global Quote": {
                "05. price": "151.50",
                "08. previous close": "150.00",
                "09. change": "1.50",
                "10. change percent": "1.0000%",
            }}

    monkeypatch.setattr(md.requests, "get", lambda *a, **kw: FakeResponse())

    q = make_service()._fetch_alpha_vantage("AAPL")
    assert q.price == 151.5
    assert q.change == 1.5
    assert q.change_percent == 1.0
    assert q.provider == "alpha_vantage"


def test_alpha_vantage_empty_payload_raises(monkeypatch):
    import src.data.market_data as md

    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-key")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {}  # rate-limited responses come back without "Global Quote"

    monkeypatch.setattr(md.requests, "get", lambda *a, **kw: FakeResponse())

    with pytest.raises(ValueError, match="no quote"):
        make_service()._fetch_alpha_vantage("AAPL")


def test_news_parsing_new_yfinance_format(monkeypatch):
    import yfinance

    FakeTicker.info = {}
    FakeTicker.news_items = [
        {"content": {
            "title": "Apple announces results",
            "provider": {"displayName": "TestWire"},
            "canonicalUrl": {"url": "https://example.com/a"},
            "pubDate": "2026-06-10",
            "summary": "Quarterly results.",
        }},
        {"content": {"title": ""}},  # untitled items are dropped
    ]
    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)

    items = make_service().get_news("AAPL")
    assert len(items) == 1
    assert items[0]["title"] == "Apple announces results"
    assert items[0]["publisher"] == "TestWire"
    assert items[0]["link"] == "https://example.com/a"


def test_news_failure_returns_empty_list(monkeypatch):
    import yfinance

    def boom(symbol):
        raise ConnectionError("feed down")

    monkeypatch.setattr(yfinance, "Ticker", boom)
    assert make_service().get_news("AAPL") == []


def test_history_stale_fallback_then_error(monkeypatch):
    import yfinance

    svc = make_service()
    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)  # .history raises

    with pytest.raises(MarketDataUnavailable, match="history"):
        svc.get_history("AAPL")

    # Seed a stale entry: it must be served when the provider is down.
    from src.data.market_data import HistoryPoint

    svc.history_cache.set("AAPL:6mo", [HistoryPoint(date="2026-01-01", close=99.0)])
    svc.history_cache._data["AAPL:6mo"].stored_at -= svc.history_cache.ttl + 100
    points = svc.get_history("AAPL")
    assert points[0].close == 99.0
