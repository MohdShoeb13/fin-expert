"""Unit tests for the TTL cache (src/data/cache.py)."""

from src.data.cache import TTLCache


def test_get_returns_fresh_value():
    cache = TTLCache(ttl_seconds=60)
    cache.set("AAPL", 200.0)
    assert cache.get("AAPL") == 200.0


def test_get_missing_returns_none():
    cache = TTLCache(ttl_seconds=60)
    assert cache.get("nope") is None


def test_expired_entry_returns_none_but_stale_survives():
    cache = TTLCache(ttl_seconds=60)
    cache.set("AAPL", 200.0)
    # Force expiry by back-dating the entry.
    cache._data["AAPL"].stored_at -= 120

    assert cache.get("AAPL") is None
    stale = cache.get_stale("AAPL")
    assert stale is not None
    assert stale.value == 200.0
    assert stale.age_seconds() >= 120


def test_set_overwrites_and_refreshes():
    cache = TTLCache(ttl_seconds=60)
    cache.set("k", 1)
    cache._data["k"].stored_at -= 120
    cache.set("k", 2)
    assert cache.get("k") == 2


def test_clear():
    cache = TTLCache(ttl_seconds=60)
    cache.set("k", 1)
    cache.clear()
    assert cache.get("k") is None
    assert cache.get_stale("k") is None
