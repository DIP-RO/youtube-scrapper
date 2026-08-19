"""media-data-extractor — A network-first YouTube data extraction toolkit.

Public API::

    from media_data_extractor import YouTubeScraper, ScraperConfig

    with YouTubeScraper() as scraper:
        result = scraper.get_video("VIDEO_ID")
        print(result.metadata.title)

    # Batch scraping with crash recovery
    with YouTubeScraper(ScraperConfig(max_workers=4)) as scraper:
        batch = scraper.batch_scrape_resilient(
            ["URL1", "URL2"], checkpoint="progress.json"
        )

    # Export to CSV
    from media_data_extractor import export_video
    csv_data = export_video(result, format="csv")

    # Video file download
    with YouTubeScraper() as scraper:
        result = scraper.download_video_file("URL", "./video.mp4", quality="720p")

    # Research dataset (one call → CSV)
    from media_data_extractor.research import collect_dataset
    rows, summary = collect_dataset(urls=["URL1"], output_path="dataset.csv")

Lightweight design:
    - ``import media_data_extractor`` loads only core modules (models, exceptions, client).
    - Heavy modules (player, pipeline, research, downloader, performance) load lazily on first access.
    - Selenium is imported lazily inside YouTubeScraper.__enter__(), not at package import time.
    - ``pip install media-data-extractor``            → core scraping + export + sentiment
    - ``pip install media-data-extractor[research]``  → + pandas integration
    - ``pip install media-data-extractor[dev]``       → + pytest, build, twine
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Eager imports — core modules needed for basic scraping
# ---------------------------------------------------------------------------
from .client import ScraperConfig, YouTubeScraper
from .exceptions import (
    AccessBlockedException,
    BrowserNotInitializedError,
    InvalidVideoURLError,
    ScraperError,
    SeleniumNotInstalledError,
    TranscriptUnavailableError,
)
from .models import (
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

# ---------------------------------------------------------------------------
# Lazy import registry — heavy modules loaded on first access
# ---------------------------------------------------------------------------
# Each entry maps an attribute name to (module_path, attribute_name).
# The attribute is loaded on first access via __getattr__.
_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # Export module
    "export_video": (".export", "export_video"),
    "export_batch": (".export", "export_batch"),
    "video_to_csv": (".export", "video_to_csv"),
    "comments_to_csv": (".export", "comments_to_csv"),
    "transcript_to_txt": (".export", "transcript_to_txt"),
    "transcript_to_srt": (".export", "transcript_to_srt"),
    "video_to_jsonl": (".export", "video_to_jsonl"),
    "video_to_xlsx": (".export", "video_to_xlsx"),
    "batch_to_csv": (".export", "batch_to_csv"),
    "batch_to_jsonl": (".export", "batch_to_jsonl"),
    "batch_to_xlsx": (".export", "batch_to_xlsx"),
    "batch_comments_to_csv": (".export", "batch_comments_to_csv"),
    "download_video": (".export", "download_video"),
    "download_batch": (".export", "download_batch"),
    # Downloader module
    "extract_streams": (".downloader", "extract_streams"),
    "download_stream": (".downloader", "download_stream"),
    "download_video_file": (".downloader", "download_video"),
    "has_ffmpeg": (".downloader", "has_ffmpeg"),
    "merge_audio_video": (".downloader", "merge_audio_video"),
    "select_best_video": (".downloader", "select_best_video"),
    "select_best_audio": (".downloader", "select_best_audio"),
    "select_best_progressive": (".downloader", "select_best_progressive"),
    "select_worst_progressive": (".downloader", "select_worst_progressive"),
    "select_by_quality": (".downloader", "select_by_quality"),
    # Sentiment module
    "analyze_sentiment": (".sentiment", "analyze_sentiment"),
    "analyze_comment_sentiment": (".sentiment", "analyze_comment_sentiment"),
    "analyze_video_sentiment": (".sentiment", "analyze_video_sentiment"),
    "SentimentResult": (".sentiment", "SentimentResult"),
    "CommentSentiment": (".sentiment", "CommentSentiment"),
    "VideoSentiment": (".sentiment", "VideoSentiment"),
    # Filters module
    "CommentFilter": (".filters", "CommentFilter"),
    "filter_comments": (".filters", "filter_comments"),
    "search_comments": (".filters", "search_comments"),
    "top_comments": (".filters", "top_comments"),
    # Player module
    "VideoPlayer": (".player", "VideoPlayer"),
    "Playlist": (".player", "Playlist"),
    "Track": (".player", "Track"),
    "save_playlist": (".player", "save_playlist"),
    "load_playlist": (".player", "load_playlist"),
    "create_playlist_from_directory": (".player", "create_playlist_from_directory"),
    "find_player_backend": (".player", "find_player_backend"),
    "has_ffplay": (".player", "has_ffplay"),
    # Pipeline module
    "ScrapePipeline": (".pipeline", "ScrapePipeline"),
    "PipelineResult": (".pipeline", "PipelineResult"),
    "PipelineStageResult": (".pipeline", "PipelineStageResult"),
    "VALID_STAGES": (".pipeline", "VALID_STAGES"),
    # Performance module
    "LRUCache": (".performance", "LRUCache"),
    "RateLimiter": (".performance", "RateLimiter"),
    "BackoffStrategy": (".performance", "BackoffStrategy"),
    "retry_with_backoff": (".performance", "retry_with_backoff"),
    "chunk_list": (".performance", "chunk_list"),
    "get_metadata_cache": (".performance", "get_metadata_cache"),
    "get_stream_cache": (".performance", "get_stream_cache"),
    "clear_all_caches": (".performance", "clear_all_caches"),
    # Research module
    "collect_dataset": (".research", "collect_dataset"),
    "collect_comment_corpus": (".research", "collect_comment_corpus"),
    "collect_transcript_corpus": (".research", "collect_transcript_corpus"),
    "collect_comparison_table": (".research", "collect_comparison_table"),
    "quick_scrape": (".research", "quick_scrape"),
    "to_dataframe": (".research", "to_dataframe"),
    "batch_to_dataframe": (".research", "batch_to_dataframe"),
    "comments_to_dataframe": (".research", "comments_to_dataframe"),
    "DatasetSummary": (".research", "DatasetSummary"),
}


def __getattr__(name: str) -> Any:
    """Lazy-load attributes from heavy modules on first access.

    This keeps ``import media_data_extractor`` fast by only loading
    core modules. Heavy modules (player, pipeline, research, etc.)
    are loaded the first time their attributes are accessed.
    """
    if name in _LAZY_EXPORTS:
        module_path, attr_name = _LAZY_EXPORTS[name]
        module = importlib.import_module(module_path, __name__)
        value = getattr(module, attr_name)
        # Cache in this module's namespace so __getattr__ isn't called again
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return all available attributes for tab-completion."""
    return sorted(list(globals().keys()) + list(_LAZY_EXPORTS.keys()))


__version__ = "4.2.0"

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
