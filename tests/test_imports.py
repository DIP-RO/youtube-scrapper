"""Tests for package imports and public API surface."""

from __future__ import annotations

import media_data_extractor
from media_data_extractor import (
    YouTubeScraper,
    ScraperConfig,
    ScraperError,
    InvalidVideoURLError,
    AccessBlockedException,
    SeleniumNotInstalledError,
    BrowserNotInitializedError,
    VideoResult,
    VideoMetadata,
    Transcript,
    TranscriptSegment,
    Comment,
    DislikeData,
    Engagement,
    Summary,
    AccessStatus,
    NetworkInfo,
    BatchResult,
    BatchError,
    StreamFormat,
    DownloadResult,
    export_video,
    export_batch,
    analyze_sentiment,
    analyze_video_sentiment,
    CommentFilter,
    filter_comments,
    download_video_file,
    extract_streams,
    has_ffmpeg,
    VideoPlayer,
    Playlist,
    Track,
    ScrapePipeline,
    PipelineResult,
    LRUCache,
    RateLimiter,
    BackoffStrategy,
    retry_with_backoff,
    chunk_list,
    collect_dataset,
    collect_comment_corpus,
    collect_transcript_corpus,
    collect_comparison_table,
    quick_scrape,
    to_dataframe,
    DatasetSummary,
)


def test_version():
    assert hasattr(media_data_extractor, "__version__")
    assert media_data_extractor.__version__ == "5.1.0"


def test_all_exports():
    expected = {
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
        # Export
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
        # Downloader (video file download)
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
        # Sentiment
        "analyze_sentiment",
        "analyze_comment_sentiment",
        "analyze_video_sentiment",
        "SentimentResult",
        "CommentSentiment",
        "VideoSentiment",
        # Filters
        "CommentFilter",
        "filter_comments",
        "search_comments",
        "top_comments",
        # Player
        "VideoPlayer",
        "Playlist",
        "Track",
        "save_playlist",
        "load_playlist",
        "create_playlist_from_directory",
        "find_player_backend",
        "has_ffplay",
        # Pipeline
        "ScrapePipeline",
        "PipelineConfig",
        "PipelineResult",
        "PipelineStageResult",
        "VALID_STAGES",
        # Performance
        "LRUCache",
        "RateLimiter",
        "BackoffStrategy",
        "retry_with_backoff",
        "chunk_list",
        "get_metadata_cache",
        "get_stream_cache",
        "clear_all_caches",
        # Research
        "collect_dataset",
        "collect_comment_corpus",
        "collect_transcript_corpus",
        "collect_comparison_table",
        "quick_scrape",
        "to_dataframe",
        "batch_to_dataframe",
        "comments_to_dataframe",
        "DatasetSummary",
    }
    assert set(media_data_extractor.__all__) == expected


def test_exception_hierarchy():
    assert issubclass(InvalidVideoURLError, ScraperError)
    assert issubclass(AccessBlockedException, ScraperError)
    assert issubclass(SeleniumNotInstalledError, ScraperError)
    assert issubclass(BrowserNotInitializedError, ScraperError)


def test_scraper_is_class():
    assert isinstance(YouTubeScraper, type)


def test_config_is_dataclass():
    config = ScraperConfig()
    assert config.headless is True
    assert config.timeout == 25


def test_player_is_class():
    assert isinstance(VideoPlayer, type)


def test_pipeline_is_class():
    assert isinstance(ScrapePipeline, type)


def test_lru_cache_is_class():
    assert isinstance(LRUCache, type)


def test_rate_limiter_is_class():
    assert isinstance(RateLimiter, type)
