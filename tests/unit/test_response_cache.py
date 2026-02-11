from __future__ import annotations

from unittest.mock import patch

from graphmind.retrieval.response_cache import CacheEntry, ResponseCache


class TestCacheEntry:
    def test_default_fields(self):
        entry = CacheEntry(key="k1", value={"answer": "yes"})
        assert entry.key == "k1"
        assert entry.value == {"answer": "yes"}
        assert entry.hits == 0
        assert entry.created_at > 0


class TestCachePutAndGet:
    def test_put_then_get_returns_value(self):
        cache = ResponseCache()
        cache.put("What is LangGraph?", {"answer": "A framework"})
        result = cache.get("What is LangGraph?")
        assert result == {"answer": "A framework"}

    def test_get_nonexistent_returns_none(self):
        cache = ResponseCache()
        result = cache.get("Unknown question")
        assert result is None

    def test_put_overwrites_existing_key(self):
        cache = ResponseCache()
        cache.put("question", {"v": 1})
        cache.put("question", {"v": 2})
        assert cache.get("question") == {"v": 2}
        assert cache.size == 1


class TestCacheKeyGeneration:
    def test_same_question_produces_same_key(self):
        key1 = ResponseCache._make_key("Hello World", "langgraph", 10)
        key2 = ResponseCache._make_key("Hello World", "langgraph", 10)
        assert key1 == key2

    def test_case_insensitive_key(self):
        key1 = ResponseCache._make_key("Hello World", "langgraph", 10)
        key2 = ResponseCache._make_key("hello world", "langgraph", 10)
        assert key1 == key2

    def test_whitespace_trimmed_key(self):
        key1 = ResponseCache._make_key("  hello  ", "langgraph", 10)
        key2 = ResponseCache._make_key("hello", "langgraph", 10)
        assert key1 == key2

    def test_different_engine_produces_different_key(self):
        key1 = ResponseCache._make_key("hello", "langgraph", 10)
        key2 = ResponseCache._make_key("hello", "crewai", 10)
        assert key1 != key2

    def test_different_top_k_produces_different_key(self):
        key1 = ResponseCache._make_key("hello", "langgraph", 5)
        key2 = ResponseCache._make_key("hello", "langgraph", 10)
        assert key1 != key2


class TestTTLExpiration:
    def test_entry_expires_after_ttl(self):
        cache = ResponseCache(ttl_seconds=60)
        # Put with real time; CacheEntry.created_at captures real monotonic
        cache.put("q", {"answer": "a"})
        key = ResponseCache._make_key("q", "langgraph", 10)
        created = cache._store[key].created_at

        with patch("graphmind.retrieval.response_cache.time") as mock_time:
            # Within TTL
            mock_time.monotonic.return_value = created + 50.0
            assert cache.get("q") == {"answer": "a"}

            # Past TTL
            mock_time.monotonic.return_value = created + 61.0
            assert cache.get("q") is None

    def test_expired_entry_is_removed_from_store(self):
        cache = ResponseCache(ttl_seconds=10)
        cache.put("q", {"a": 1})
        assert cache.size == 1
        key = ResponseCache._make_key("q", "langgraph", 10)
        created = cache._store[key].created_at

        with patch("graphmind.retrieval.response_cache.time") as mock_time:
            mock_time.monotonic.return_value = created + 11.0
            cache.get("q")  # triggers removal
            assert cache.size == 0


class TestLRUEviction:
    def test_evicts_oldest_when_max_size_exceeded(self):
        cache = ResponseCache(max_size=2)
        cache.put("q1", {"v": 1})
        cache.put("q2", {"v": 2})
        cache.put("q3", {"v": 3})
        # q1 should have been evicted
        assert cache.get("q1") is None
        assert cache.get("q2") == {"v": 2}
        assert cache.get("q3") == {"v": 3}
        assert cache.size == 2

    def test_recently_accessed_not_evicted(self):
        cache = ResponseCache(max_size=2)
        cache.put("q1", {"v": 1})
        cache.put("q2", {"v": 2})
        # Access q1 so it becomes most-recently-used
        cache.get("q1")
        # Insert q3 -> should evict q2 (least recently used)
        cache.put("q3", {"v": 3})
        assert cache.get("q1") == {"v": 1}
        assert cache.get("q2") is None
        assert cache.get("q3") == {"v": 3}


class TestInvalidate:
    def test_invalidate_single_entry(self):
        cache = ResponseCache()
        cache.put("q1", {"v": 1})
        cache.put("q2", {"v": 2})
        cache.invalidate("q1")
        assert cache.get("q1") is None
        assert cache.get("q2") == {"v": 2}

    def test_invalidate_all_entries(self):
        cache = ResponseCache()
        cache.put("q1", {"v": 1})
        cache.put("q2", {"v": 2})
        cache.invalidate(None)
        assert cache.size == 0
        assert cache.get("q1") is None
        assert cache.get("q2") is None

    def test_invalidate_nonexistent_is_noop(self):
        cache = ResponseCache()
        cache.put("q1", {"v": 1})
        cache.invalidate("nonexistent")
        assert cache.size == 1


class TestHitRateAndStats:
    def test_hit_rate_zero_when_empty(self):
        cache = ResponseCache()
        assert cache.hit_rate == 0.0

    def test_hit_rate_after_hits_and_misses(self):
        cache = ResponseCache()
        cache.put("q1", {"v": 1})
        cache.get("q1")  # hit
        cache.get("q1")  # hit
        cache.get("q2")  # miss
        # 2 hits, 1 miss -> 2/3
        assert abs(cache.hit_rate - 2 / 3) < 0.01

    def test_stats_returns_all_keys(self):
        cache = ResponseCache(max_size=100, ttl_seconds=300)
        cache.put("q1", {"v": 1})
        cache.get("q1")  # hit
        cache.get("q2")  # miss

        s = cache.stats()
        assert s["size"] == 1
        assert s["max_size"] == 100
        assert s["ttl_seconds"] == 300
        assert s["total_hits"] == 1
        assert s["total_misses"] == 1
        assert s["hit_rate"] == 0.5

    def test_cache_miss_increments_miss_count(self):
        cache = ResponseCache()
        cache.get("nonexistent")
        cache.get("also_nonexistent")
        assert cache.stats()["total_misses"] == 2
        assert cache.stats()["total_hits"] == 0
