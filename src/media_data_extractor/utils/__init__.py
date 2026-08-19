"""Shared utilities — helpers, performance optimizations.

Import from here::

    from media_data_extractor.utils import extract_video_id, detect_access_block
    from media_data_extractor.utils import LRUCache, RateLimiter, retry_with_backoff
"""

from __future__ import annotations

from .helpers import (
    detect_access_block,
    extract_video_id,
    find_all_keys,
    find_key,
    int_or_none,
    summarize_text,
)

# Performance is lazy-loaded to keep the package lightweight
_LAZY = {
    "LRUCache": (".performance", "LRUCache"),
    "RateLimiter": (".performance", "RateLimiter"),
    "BackoffStrategy": (".performance", "BackoffStrategy"),
    "retry_with_backoff": (".performance", "retry_with_backoff"),
    "chunk_list": (".performance", "chunk_list"),
    "get_metadata_cache": (".performance", "get_metadata_cache"),
    "get_stream_cache": (".performance", "get_stream_cache"),
    "clear_all_caches": (".performance", "clear_all_caches"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr_name = _LAZY[name]
        import importlib
        module = importlib.import_module(module_path, __name__)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "extract_video_id",
    "detect_access_block",
    "find_all_keys",
    "find_key",
    "int_or_none",
    "summarize_text",
    "LRUCache",
    "RateLimiter",
    "BackoffStrategy",
    "retry_with_backoff",
    "chunk_list",
    "get_metadata_cache",
    "get_stream_cache",
    "clear_all_caches",
]
