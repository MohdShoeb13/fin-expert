"""TTL cache for market data (30-minute TTL per project FAQ).

Keeps expired entries around so the system can degrade gracefully: when all
data providers fail, stale data with a freshness warning beats no data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    stored_at: float

    def age_seconds(self) -> float:
        return time.time() - self.stored_at


class TTLCache:
    def __init__(self, ttl_seconds: float):
        self.ttl = ttl_seconds
        self._data: dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        """Return a fresh value, or None if missing/expired."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None or entry.age_seconds() > self.ttl:
                return None
            return entry.value

    def get_stale(self, key: str) -> CacheEntry | None:
        """Return the entry even if expired (for graceful degradation)."""
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = CacheEntry(value=value, stored_at=time.time())

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
