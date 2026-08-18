"""Tests for performance optimization utilities."""

from __future__ import annotations

import time

import pytest

from yt_network_scraper.performance import (
    BackoffStrategy,
    LRUCache,
    RateLimiter,
    chunk_list,
    clear_all_caches,
    get_metadata_cache,
    get_stream_cache,
    retry_with_backoff,
)


class TestLRUCache:
    def test_put_and_get(self):
        cache = LRUCache(maxsize=10)
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_returns_none(self):
        cache = LRUCache(maxsize=10)
        assert cache.get("nonexistent") is None

    def test_eviction_lru(self):
        cache = LRUCache(maxsize=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Access "a" to make it recently used
        cache.get("a")
        # Put "d" — should evict "b" (LRU)
        cache.put("d", 4)
        assert cache.get("b") is None
        assert cache.get("a") == 1
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_size(self):
        cache = LRUCache(maxsize=10)
        cache.put("a", 1)
        cache.put("b", 2)
        assert cache.size == 2

    def test_clear(self):
        cache = LRUCache(maxsize=10)
        cache.put("a", 1)
        cache.clear()
        assert cache.size == 0
        assert cache.get("a") is None

    def test_hit_rate(self):
        cache = LRUCache(maxsize=10)
        cache.put("a", 1)
        cache.get("a")  # hit
        cache.get("b")  # miss
        assert cache.hit_rate == 0.5

    def test_stats(self):
        cache = LRUCache(maxsize=10)
        cache.put("a", 1)
        cache.get("a")
        stats = cache.stats
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 0

    def test_get_or_compute_cached(self):
        cache = LRUCache(maxsize=10)
        cache.put("key", "cached_value")
        result = cache.get_or_compute("key", lambda: "computed")
        assert result == "cached_value"

    def test_get_or_compute_new(self):
        cache = LRUCache(maxsize=10)
        result = cache.get_or_compute("new_key", lambda: "computed")
        assert result == "computed"
        assert cache.get("new_key") == "computed"

    def test_overwrite_existing_key(self):
        cache = LRUCache(maxsize=10)
        cache.put("a", 1)
        cache.put("a", 2)
        assert cache.get("a") == 2
        assert cache.size == 1

    def test_thread_safe(self):
        """Test that the cache is thread-safe under concurrent access."""
        import threading

        cache = LRUCache(maxsize=1000)
        errors: list[Exception] = []

        def worker():
            try:
                for i in range(100):
                    cache.put(f"key_{i}", i)
                    cache.get(f"key_{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


class TestRateLimiter:
    def test_acquire_immediate(self):
        limiter = RateLimiter(rate=10.0, burst=10)
        # With burst=10, first 10 acquires should be immediate
        for _ in range(10):
            assert limiter.try_acquire() is True

    def test_try_acquire_depleted(self):
        limiter = RateLimiter(rate=1.0, burst=1)
        assert limiter.try_acquire() is True
        assert limiter.try_acquire() is False  # No tokens left

    def test_acquire_with_wait(self):
        limiter = RateLimiter(rate=10.0, burst=1)
        limiter.acquire()  # First acquire uses the burst token
        # Second acquire should wait ~0.1s
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.05  # At least some wait

    def test_rate_limiter_does_not_block_forever(self):
        limiter = RateLimiter(rate=1.0, burst=1)
        limiter.acquire()
        # Should timeout, not block forever
        assert limiter.acquire(timeout=0.05) is False


class TestBackoffStrategy:
    def test_delay_increases(self):
        strat = BackoffStrategy(initial_delay=1.0, multiplier=2.0, jitter=0)
        assert strat.delay(0) == 1.0
        assert strat.delay(1) == 2.0
        assert strat.delay(2) == 4.0

    def test_max_delay_cap(self):
        strat = BackoffStrategy(initial_delay=1.0, max_delay=5.0, multiplier=2.0, jitter=0)
        assert strat.delay(10) == 5.0  # Capped

    def test_jitter_in_range(self):
        strat = BackoffStrategy(initial_delay=10.0, multiplier=1.0, jitter=0.2)
        for _ in range(20):
            delay = strat.delay(0)
            assert 8.0 <= delay <= 12.0  # 10 ± 20%

    def test_zero_jitter(self):
        strat = BackoffStrategy(initial_delay=5.0, multiplier=2.0, jitter=0)
        assert strat.delay(0) == 5.0
        assert strat.delay(1) == 10.0


class TestRetryWithBackoff:
    def test_succeeds_first_try(self):
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = retry_with_backoff(func, max_retries=3)
        assert result == "success"
        assert call_count == 1

    def test_retries_on_failure(self):
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "success"

        strat = BackoffStrategy(initial_delay=0.01, multiplier=1.0, jitter=0)
        result = retry_with_backoff(func, max_retries=3, strategy=strat)
        assert result == "success"
        assert call_count == 3

    def test_exhausts_retries(self):
        def func():
            raise ValueError("always fails")

        strat = BackoffStrategy(initial_delay=0.01, multiplier=1.0, jitter=0)
        with pytest.raises(ValueError, match="always fails"):
            retry_with_backoff(func, max_retries=2, strategy=strat)

    def test_only_catches_specified_exceptions(self):
        def func():
            raise TypeError("wrong type")

        strat = BackoffStrategy(initial_delay=0.01, jitter=0)
        with pytest.raises(TypeError):
            retry_with_backoff(func, max_retries=3, strategy=strat, exceptions=(ValueError,))


class TestChunkList:
    def test_basic_chunking(self):
        items = list(range(10))
        chunks = chunk_list(items, chunk_size=3)
        assert len(chunks) == 4  # 3+3+3+1
        assert chunks[0] == [0, 1, 2]
        assert chunks[3] == [9]

    def test_chunk_size_larger_than_list(self):
        items = [1, 2, 3]
        chunks = chunk_list(items, chunk_size=10)
        assert len(chunks) == 1
        assert chunks[0] == [1, 2, 3]

    def test_empty_list(self):
        chunks = chunk_list([], chunk_size=5)
        assert chunks == []

    def test_chunk_size_zero_returns_whole_list(self):
        items = [1, 2, 3]
        chunks = chunk_list(items, chunk_size=0)
        assert len(chunks) == 1
        assert chunks[0] == [1, 2, 3]

    def test_exact_division(self):
        items = list(range(6))
        chunks = chunk_list(items, chunk_size=2)
        assert len(chunks) == 3
        assert all(len(c) == 2 for c in chunks)


class TestGlobalCaches:
    def test_metadata_cache(self):
        cache = get_metadata_cache()
        assert cache is not None
        assert isinstance(cache, LRUCache)

    def test_stream_cache(self):
        cache = get_stream_cache()
        assert cache is not None
        assert isinstance(cache, LRUCache)

    def test_clear_all_caches(self):
        get_metadata_cache().put("a", 1)
        get_stream_cache().put("b", 2)
        clear_all_caches()
        assert get_metadata_cache().size == 0
        assert get_stream_cache().size == 0
