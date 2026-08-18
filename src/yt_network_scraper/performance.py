"""Performance optimization utilities for high-load scenarios.

Provides:
- **LRU cache** for frequently accessed data (video metadata, stream URLs)
- **Rate limiter** with token bucket algorithm for API throttling
- **Exponential backoff** for retry logic under load
- **Connection pool** for HTTP session reuse
- **Batch processor** with memory-efficient chunking

These utilities help the scraper handle high-volume batch jobs (1000+ videos)
without overwhelming YouTube's servers or running out of memory.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# LRU Cache — O(1) get/put with thread safety
# ---------------------------------------------------------------------------

class LRUCache:
    """Thread-safe LRU (Least Recently Used) cache.

    Uses OrderedDict for O(1) access and eviction.
    Thread-safe via a re-entrant lock.

    Example::

        cache = LRUCache(maxsize=500)
        cache.put("key", value)
        value = cache.get("key")  # Returns None if not found
    """

    def __init__(self, maxsize: int = 500) -> None:
        self.maxsize = maxsize
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get a value from the cache. Returns None if not found."""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._hits += 1
                return self._data[key]
            self._misses += 1
            return None

    def put(self, key: str, value: Any) -> None:
        """Put a value into the cache, evicting the LRU item if full."""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._data[key] = value
            else:
                if len(self._data) >= self.maxsize:
                    self._data.popitem(last=False)  # Evict LRU
                self._data[key] = value

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> Any:
        """Get from cache, or compute and cache the value.

        Equivalent to::

            value = cache.get(key)
            if value is None:
                value = compute()
                cache.put(key, value)
        """
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._hits += 1
                return self._data[key]
        value = compute()
        self.put(key, value)
        return value

    def clear(self) -> None:
        """Clear all cached items."""
        with self._lock:
            self._data.clear()
            self._hits = 0
            self._misses = 0

    @property
    def size(self) -> int:
        """Number of items currently cached."""
        with self._lock:
            return len(self._data)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict[str, Any]:
        """Cache statistics."""
        with self._lock:
            return {
                "size": len(self._data),
                "maxsize": self.maxsize,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self.hit_rate, 4),
            }


# ---------------------------------------------------------------------------
# Token Bucket Rate Limiter — O(1) acquire
# ---------------------------------------------------------------------------

class RateLimiter:
    """Token bucket rate limiter for API throttling.

    Limits the rate of operations to prevent overwhelming YouTube's
    servers. Thread-safe.

    Args:
        rate: Maximum operations per second.
        burst: Maximum burst size (default: same as rate).

    Example::

        limiter = RateLimiter(rate=2.0)  # 2 ops/sec
        limiter.acquire()  # Blocks until allowed
        do_api_call()
    """

    def __init__(self, rate: float = 2.0, burst: int | None = None) -> None:
        self.rate = max(0.1, rate)
        self.burst = burst or int(rate)
        self._tokens = float(self.burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: float | None = None) -> bool:
        """Acquire a token, blocking if necessary.

        Args:
            timeout: Maximum seconds to wait. None = wait forever.

        Returns:
            True if a token was acquired, False if timed out.
        """
        deadline = time.monotonic() + timeout if timeout else None
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                # Calculate wait time
                needed = 1.0 - self._tokens
                wait = needed / self.rate
            if deadline and time.monotonic() + wait > deadline:
                return False
            time.sleep(min(wait, 0.1))

    def try_acquire(self) -> bool:
        """Try to acquire a token without blocking.

        Returns:
            True if acquired, False if would need to wait.
        """
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)


# ---------------------------------------------------------------------------
# Exponential Backoff — retry with jitter
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BackoffStrategy:
    """Exponential backoff configuration with jitter.

    Attributes:
        initial_delay: Initial delay in seconds.
        max_delay: Maximum delay cap.
        multiplier: Delay multiplier per attempt.
        jitter: Jitter fraction (0.0 = no jitter, 1.0 = full jitter).
    """

    initial_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter: float = 0.1

    def delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (0-based).

        Uses exponential growth with jitter to avoid thundering herd.

        Args:
            attempt: Attempt number (0 = first retry).

        Returns:
            Delay in seconds.
        """
        import random

        base = min(
            self.initial_delay * (self.multiplier ** attempt),
            self.max_delay,
        )
        if self.jitter > 0:
            jitter_amount = base * self.jitter
            base += random.uniform(-jitter_amount, jitter_amount)
        return max(0.0, base)


def retry_with_backoff(
    func: Callable[..., Any],
    max_retries: int = 3,
    strategy: BackoffStrategy | None = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Retry a function with exponential backoff.

    Args:
        func: Function to call.
        max_retries: Maximum number of retries.
        strategy: Backoff strategy (default: 1s initial, 2x multiplier).
        exceptions: Exception types to catch and retry.
        *args: Positional arguments for func.
        **kwargs: Keyword arguments for func.

    Returns:
        The return value of func on success.

    Raises:
        The last exception if all retries are exhausted.
    """
    strat = strategy or BackoffStrategy()
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            delay = strat.delay(attempt)
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Batch chunker — memory-efficient large batch processing
# ---------------------------------------------------------------------------

def chunk_list(items: list[Any], chunk_size: int) -> list[list[Any]]:
    """Split a list into chunks of at most *chunk_size* items.

    Args:
        items: List to chunk.
        chunk_size: Maximum chunk size.

    Returns:
        List of chunks (each a list).
    """
    if chunk_size <= 0:
        return [items]
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


# ---------------------------------------------------------------------------
# Global cache instances — shared across scraper instances
# ---------------------------------------------------------------------------

# Cache for video metadata (avoids re-scraping the same video)
_metadata_cache = LRUCache(maxsize=1000)

# Cache for stream URLs (avoids re-loading watch page for download)
_stream_cache = LRUCache(maxsize=500)


def get_metadata_cache() -> LRUCache:
    """Get the global metadata cache."""
    return _metadata_cache


def get_stream_cache() -> LRUCache:
    """Get the global stream URL cache."""
    return _stream_cache


def clear_all_caches() -> None:
    """Clear all global caches."""
    _metadata_cache.clear()
    _stream_cache.clear()
