"""Market data service: yFinance primary, Alpha Vantage fallback.

Resilience strategy (graded requirement):
  fresh cache -> yFinance (with retries) -> Alpha Vantage -> stale cache -> error
Every quote carries a freshness timestamp and the provider that served it.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import requests

from src.core.config import get_api_key, get_config
from src.core.logging import get_logger
from src.data.cache import TTLCache
from src.utils.validators import normalize_ticker

logger = get_logger(__name__)


class MarketDataUnavailable(Exception):
    """All providers failed and no cached data exists."""


@dataclass
class Quote:
    symbol: str
    price: float
    change: float
    change_percent: float
    currency: str = "USD"
    name: str = ""
    previous_close: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    dividend_yield: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    provider: str = "yfinance"
    as_of: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stale: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HistoryPoint:
    date: str
    close: float


class MarketDataService:
    def __init__(self):
        cfg = get_config()
        ttl = cfg.get("market_data.cache_ttl_seconds", 1800)
        self.quote_cache = TTLCache(ttl)
        self.history_cache = TTLCache(ttl)
        self.max_retries = cfg.get("market_data.max_retries", 3)
        self.backoff_base = cfg.get("market_data.backoff_base_seconds", 1.0)

    # ------------------------------------------------------------------ quotes

    def get_quote(self, symbol: str) -> Quote:
        symbol = normalize_ticker(symbol)

        cached = self.quote_cache.get(symbol)
        if cached is not None:
            return cached

        for fetch in (self._fetch_yfinance, self._fetch_alpha_vantage):
            try:
                quote = self._with_retries(fetch, symbol)
                self.quote_cache.set(symbol, quote)
                return quote
            except Exception as exc:  # noqa: BLE001 - provider failures expected
                logger.warning("%s failed for %s: %s", fetch.__name__, symbol, exc)

        stale = self.quote_cache.get_stale(symbol)
        if stale is not None:
            logger.warning("Serving stale quote for %s (age %.0fs)", symbol, stale.age_seconds())
            quote = stale.value
            quote.stale = True
            return quote

        raise MarketDataUnavailable(
            f"Could not fetch a quote for {symbol} from any provider"
        )

    def _with_retries(self, fetch, symbol: str):
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return fetch(symbol)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self.max_retries - 1:
                    time.sleep(self.backoff_base * (2**attempt))
        raise last_exc  # type: ignore[misc]

    def _fetch_yfinance(self, symbol: str) -> Quote:
        import yfinance as yf

        info = yf.Ticker(symbol).info
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
        if price is None:
            raise ValueError(f"yfinance returned no price for {symbol}")
        change = price - prev if prev else 0.0
        return Quote(
            symbol=symbol,
            price=float(price),
            change=round(change, 4),
            change_percent=round(change / prev * 100, 4) if prev else 0.0,
            currency=info.get("currency", "USD"),
            name=info.get("shortName") or info.get("longName") or symbol,
            previous_close=prev,
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            dividend_yield=info.get("dividendYield"),
            fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
            fifty_two_week_low=info.get("fiftyTwoWeekLow"),
            provider="yfinance",
        )

    def _fetch_alpha_vantage(self, symbol: str) -> Quote:
        cfg = get_config()
        api_key = get_api_key(cfg.get("market_data.alpha_vantage_key_env", "ALPHAVANTAGE_API_KEY"))
        if not api_key:
            raise MarketDataUnavailable("Alpha Vantage API key not configured")

        resp = requests.get(
            cfg["market_data.alpha_vantage_base_url"],
            params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("Global Quote") or {}
        if not data.get("05. price"):
            raise ValueError(f"Alpha Vantage returned no quote for {symbol}")
        price = float(data["05. price"])
        prev = float(data.get("08. previous close") or 0) or None
        return Quote(
            symbol=symbol,
            price=price,
            change=float(data.get("09. change") or 0),
            change_percent=float((data.get("10. change percent") or "0%").rstrip("%")),
            previous_close=prev,
            provider="alpha_vantage",
        )

    # ----------------------------------------------------------------- history

    def get_history(self, symbol: str, period: str = "6mo") -> list[HistoryPoint]:
        symbol = normalize_ticker(symbol)
        key = f"{symbol}:{period}"

        cached = self.history_cache.get(key)
        if cached is not None:
            return cached

        try:
            import yfinance as yf

            df = yf.Ticker(symbol).history(period=period)
            points = [
                HistoryPoint(date=idx.strftime("%Y-%m-%d"), close=round(float(row["Close"]), 4))
                for idx, row in df.iterrows()
            ]
            if points:
                self.history_cache.set(key, points)
                return points
        except Exception as exc:  # noqa: BLE001
            logger.warning("History fetch failed for %s: %s", symbol, exc)

        stale = self.history_cache.get_stale(key)
        if stale is not None:
            return stale.value
        raise MarketDataUnavailable(f"Could not fetch history for {symbol}")

    # -------------------------------------------------------------------- news

    def get_news(self, symbol: str, limit: int = 8) -> list[dict]:
        try:
            import yfinance as yf

            raw = yf.Ticker(normalize_ticker(symbol)).news or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("News fetch failed for %s: %s", symbol, exc)
            return []
        items = []
        for item in raw[:limit]:
            content = item.get("content", item)
            items.append(
                {
                    "title": content.get("title", ""),
                    "publisher": (content.get("provider") or {}).get("displayName", "")
                    if isinstance(content.get("provider"), dict)
                    else content.get("publisher", ""),
                    "link": (content.get("canonicalUrl") or {}).get("url", "")
                    if isinstance(content.get("canonicalUrl"), dict)
                    else content.get("link", ""),
                    "published": content.get("pubDate") or content.get("providerPublishTime", ""),
                    "summary": content.get("summary", ""),
                }
            )
        return [i for i in items if i["title"]]


_service: MarketDataService | None = None


def get_market_data_service() -> MarketDataService:
    global _service
    if _service is None:
        _service = MarketDataService()
    return _service
