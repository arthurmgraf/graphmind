"""LRU response cache for query results with TTL expiration."""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_MAX_SIZE = 256
_DEFAULT_TTL_SECONDS = 300  # 5 minutes


@dataclass
class CacheEntry:
    key: str
    value: dict
    created_at: float = field(default_factory=time.monotonic)
    hits: int = 0


class ResponseCache:
    """Bounded LRU cache with TTL for query responses.

    Thread-safe for single-process asyncio usage.
    """

    def __init__(
        self,
        max_size: int = _DEFAULT_MAX_SIZE,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._total_hits = 0
        self._total_misses = 0

    @staticmethod
    def _make_key(question: str, engine: str, top_k: int) -> str:
        raw = f"{question.strip().lower()}|{engine}|{top_k}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, question: str, engine: str = "langgraph", top_k: int = 10) -> dict | None:
        key = self._make_key(question, engine, top_k)
        entry = self._store.get(key)
        if entry is None:
            self._total_misses += 1
            return None

        if (time.monotonic() - entry.created_at) > self._ttl:
            del self._store[key]
            self._total_misses += 1
            logger.debug("cache_expired", key=key)
            return None

        self._store.move_to_end(key)
        entry.hits += 1
        self._total_hits += 1
        logger.debug("cache_hit", key=key, hits=entry.hits)
        return entry.value

    def put(self, question: str, response: dict, engine: str = "langgraph", top_k: int = 10) -> None:
        key = self._make_key(question, engine, top_k)
        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = CacheEntry(key=key, value=response)
            return

        if len(self._store) >= self._max_size:
            self._store.popitem(last=False)

        self._store[key] = CacheEntry(key=key, value=response)
        logger.debug("cache_put", key=key, size=len(self._store))

    def invalidate(self, question: str | None = None, engine: str = "langgraph", top_k: int = 10) -> None:
        if question is None:
            self._store.clear()
            logger.info("cache_cleared")
            return
        key = self._make_key(question, engine, top_k)
        self._store.pop(key, None)

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def hit_rate(self) -> float:
        total = self._total_hits + self._total_misses
        return self._total_hits / total if total > 0 else 0.0

    def stats(self) -> dict:
        return {
            "size": self.size,
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
            "total_hits": self._total_hits,
            "total_misses": self._total_misses,
            "hit_rate": round(self.hit_rate, 3),
        }
