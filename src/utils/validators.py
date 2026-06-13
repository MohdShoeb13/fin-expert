"""Input validation helpers shared by the API layer and agents."""

from __future__ import annotations

import re

# Allows a leading "^" for index symbols (e.g. ^GSPC, ^IXIC, ^DJI).
_TICKER_RE = re.compile(r"^\^?[A-Z][A-Z0-9.\-]{0,9}$")


def normalize_ticker(symbol: str) -> str:
    """Uppercase/strip a ticker symbol, raising ValueError if malformed."""
    cleaned = symbol.strip().upper()
    if not _TICKER_RE.match(cleaned):
        raise ValueError(f"Invalid ticker symbol: {symbol!r}")
    return cleaned


def validate_positive(value: float, name: str) -> float:
    if value is None or value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return float(value)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
