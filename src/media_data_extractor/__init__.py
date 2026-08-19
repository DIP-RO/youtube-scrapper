"""media-data-extractor — A network-first YouTube data extraction toolkit.

Industry-standard platform-based architecture::

    media_data_extractor/
    ├── core/          # Platform-agnostic models, exceptions, base classes
    ├── platforms/     # Platform implementations
    │   └── youtube/   # YouTube scraper, parser, downloader
    ├── exporters/     # CSV, JSON, JSONL, XLSX, SRT, TXT exports
    ├── analytics/     # Sentiment, filters, research helpers
    ├── media/         # Video player, pipeline orchestration
    ├── utils/         # Performance utilities, helpers
    └── cli/           # Command-line interface

Public API (backward compatible)::

    from media_data_extractor import YouTubeScraper, ScraperConfig

    with YouTubeScraper() as scraper:
        result = scraper.get_video("VIDEO_ID")
        print(result.metadata.title)

Lightweight design:
    - ``import media_data_extractor`` loads only core modules.
    - Heavy modules (player, pipeline, research, downloader) load lazily.
    - ``from media_data_extractor.core import YouTubeScraper`` — lightest path.
    - ``pip install media-data-extractor``            → core scraping + export
    - ``pip install media-data-extractor[research]``  → + pandas integration
    - ``pip install media-data-extractor[dev]``       → + pytest, build, twine
"""

from __future__ import annotations

import importlib
from typing import Any

# ---------------------------------------------------------------------------
# Eager imports — core modules needed for basic scraping
# ---------------------------------------------------------------------------
from .core.exceptions import (
    AccessBlockedException,
    BrowserNotInitializedError,
    InvalidVideoURLError,
    NetworkRequestError,
    ScraperError,
    SeleniumNotInstalledError,
    TranscriptUnavailableError,
)
from .core.models import (
    AccessStatus,
    BatchError,
    BatchResult,
    Comment,
    DislikeData,
    DownloadResult,
    Engagement,
    NetworkInfo,
    StreamFormat,
    Summary,
    Transcript,
    TranscriptSegment,
    VideoMetadata,
    VideoResult,
)
from .platforms.youtube.scraper import ScraperConfig, YouTubeScraper

# ---------------------------------------------------------------------------
# Lazy import registry — heavy modules loaded on first access
# ---------------------------------------------------------------------------
_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # Exporters
    "export_video": (".exporters._all", "export_video"),
    "export_batch": (".exporters._all", "export_batch"),
    "video_to_csv": (".exporters._all", "video_to_csv"),
    "comments_to_csv": (".exporters._all", "comments_to_csv"),
    "transcript_to_txt": (".exporters._all", "transcript_to_txt"),
    "transcript_to_srt": (".exporters._all", "transcript_to_srt"),
    "video_to_jsonl": (".exporters._all", "video_to_jsonl"),
    "video_to_xlsx": (".exporters._all", "video_to_xlsx"),
    "batch_to_csv": (".exporters._all", "batch_to_csv"),
    "batch_to_jsonl": (".exporters._all", "batch_to_jsonl"),
    "batch_to_xlsx": (".exporters._all", "batch_to_xlsx"),
    "batch_comments_to_csv": (".exporters._all", "batch_comments_to_csv"),
    "download_video": (".exporters._all", "download_video"),
    "download_batch": (".exporters._all", "download_batch"),
    # Downloader (YouTube)
    "extract_streams": (".platforms.youtube.downloader", "extract_streams"),
    "download_stream": (".platforms.youtube.downloader", "download_stream"),
    "download_video_file": (".platforms.youtube.downloader", "download_video"),
    "has_ffmpeg": (".platforms.youtube.downloader", "has_ffmpeg"),
    "merge_audio_video": (".platforms.youtube.downloader", "merge_audio_video"),
    "select_best_video": (".platforms.youtube.downloader", "select_best_video"),
    "select_best_audio": (".platforms.youtube.downloader", "select_best_audio"),
    "select_best_progressive": (".platforms.youtube.downloader", "select_best_progressive"),
    "select_worst_progressive": (".platforms.youtube.downloader", "select_worst_progressive"),
    "select_by_quality": (".platforms.youtube.downloader", "select_by_quality"),
    # Analytics — sentiment
    "analyze_sentiment": (".analytics.sentiment", "analyze_sentiment"),
    "analyze_comment_sentiment": (".analytics.sentiment", "analyze_comment_sentiment"),
    "analyze_video_sentiment": (".analytics.sentiment", "analyze_video_sentiment"),
    "SentimentResult": (".analytics.sentiment", "SentimentResult"),
    "CommentSentiment": (".analytics.sentiment", "CommentSentiment"),
    "VideoSentiment": (".analytics.sentiment", "VideoSentiment"),
    # Analytics — filters
    "CommentFilter": (".analytics.filters", "CommentFilter"),
    "filter_comments": (".analytics.filters", "filter_comments"),
    "search_comments": (".analytics.filters", "search_comments"),
    "top_comments": (".analytics.filters", "top_comments"),
    # Media — player
    "VideoPlayer": (".media.player", "VideoPlayer"),
    "Playlist": (".media.player", "Playlist"),
    "Track": (".media.player", "Track"),
    "save_playlist": (".media.player", "save_playlist"),
    "load_playlist": (".media.player", "load_playlist"),
    "create_playlist_from_directory": (".media.player", "create_playlist_from_directory"),
    "find_player_backend": (".media.player", "find_player_backend"),
    "has_ffplay": (".media.player", "has_ffplay"),
    # Media — pipeline
    "ScrapePipeline": (".media.pipeline", "ScrapePipeline"),
    "PipelineConfig": (".media.pipeline", "PipelineConfig"),
    "PipelineResult": (".media.pipeline", "PipelineResult"),
    "PipelineStageResult": (".media.pipeline", "PipelineStageResult"),
    "VALID_STAGES": (".media.pipeline", "VALID_STAGES"),
    # Utils — performance
    "LRUCache": (".utils.performance", "LRUCache"),
    "RateLimiter": (".utils.performance", "RateLimiter"),
    "BackoffStrategy": (".utils.performance", "BackoffStrategy"),
    "retry_with_backoff": (".utils.performance", "retry_with_backoff"),
    "chunk_list": (".utils.performance", "chunk_list"),
    "get_metadata_cache": (".utils.performance", "get_metadata_cache"),
    "get_stream_cache": (".utils.performance", "get_stream_cache"),
    "clear_all_caches": (".utils.performance", "clear_all_caches"),
    # Analytics — research
    "collect_dataset": (".analytics.research", "collect_dataset"),
    "collect_comment_corpus": (".analytics.research", "collect_comment_corpus"),
    "collect_transcript_corpus": (".analytics.research", "collect_transcript_corpus"),
    "collect_comparison_table": (".analytics.research", "collect_comparison_table"),
    "quick_scrape": (".analytics.research", "quick_scrape"),
    "to_dataframe": (".analytics.research", "to_dataframe"),
    "batch_to_dataframe": (".analytics.research", "batch_to_dataframe"),
    "comments_to_dataframe": (".analytics.research", "comments_to_dataframe"),
    "DatasetSummary": (".analytics.research", "DatasetSummary"),
}


def __getattr__(name: str) -> Any:
    """Lazy-load attributes from heavy modules on first access."""
    if name in _LAZY_EXPORTS:
        module_path, attr_name = _LAZY_EXPORTS[name]
        module = importlib.import_module(module_path, __name__)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return all available attributes for tab-completion."""
    return sorted(list(globals().keys()) + list(_LAZY_EXPORTS.keys()))


__version__ = "5.1.2"

__all__ = [
    # Core (eagerly loaded)
    "YouTubeScraper",
    "ScraperConfig",
    "ScraperError",
    "InvalidVideoURLError",
    "AccessBlockedException",
    "SeleniumNotInstalledError",
    "BrowserNotInitializedError",
    "TranscriptUnavailableError",
    "NetworkRequestError",
    "VideoResult",
    "VideoMetadata",
    "Transcript",
    "TranscriptSegment",
    "Comment",
    "DislikeData",
    "Engagement",
    "Summary",
    "AccessStatus",
    "NetworkInfo",
    "BatchResult",
    "BatchError",
    "StreamFormat",
    "DownloadResult",
    # Lazy-loaded
    "export_video",
    "export_batch",
    "video_to_csv",
    "comments_to_csv",
    "transcript_to_txt",
    "transcript_to_srt",
    "video_to_jsonl",
    "video_to_xlsx",
    "batch_to_csv",
    "batch_to_jsonl",
    "batch_to_xlsx",
    "batch_comments_to_csv",
    "download_video",
    "download_batch",
    "extract_streams",
    "download_stream",
    "download_video_file",
    "has_ffmpeg",
    "merge_audio_video",
    "select_best_video",
    "select_best_audio",
    "select_best_progressive",
    "select_worst_progressive",
    "select_by_quality",
    "analyze_sentiment",
    "analyze_comment_sentiment",
    "analyze_video_sentiment",
    "SentimentResult",
    "CommentSentiment",
    "VideoSentiment",
    "CommentFilter",
    "filter_comments",
    "search_comments",
    "top_comments",
    "VideoPlayer",
    "Playlist",
    "Track",
    "save_playlist",
    "load_playlist",
    "create_playlist_from_directory",
    "find_player_backend",
    "has_ffplay",
    "ScrapePipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStageResult",
    "VALID_STAGES",
    "LRUCache",
    "RateLimiter",
    "BackoffStrategy",
    "retry_with_backoff",
    "chunk_list",
    "get_metadata_cache",
    "get_stream_cache",
    "clear_all_caches",
    "collect_dataset",
    "collect_comment_corpus",
    "collect_transcript_corpus",
    "collect_comparison_table",
    "quick_scrape",
    "to_dataframe",
    "batch_to_dataframe",
    "comments_to_dataframe",
    "DatasetSummary",
]
