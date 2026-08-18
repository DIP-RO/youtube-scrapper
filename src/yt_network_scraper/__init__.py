"""yt-network-scraper — A network-first YouTube video scraper and downloader.

Public API::

    from yt_network_scraper import YouTubeScraper, ScraperConfig

    with YouTubeScraper() as scraper:
        result = scraper.get_video("VIDEO_ID")
        print(result.metadata.title)

    # Batch scraping with crash recovery
    with YouTubeScraper(ScraperConfig(max_workers=4)) as scraper:
        batch = scraper.batch_scrape_resilient(
            ["URL1", "URL2"], checkpoint="progress.json"
        )

    # Export to CSV
    from yt_network_scraper import export_video
    csv_data = export_video(result, format="csv")

    # Sentiment analysis
    from yt_network_scraper import analyze_video_sentiment
    sentiment = analyze_video_sentiment(result)
    print(sentiment.overall_label)

    # Comment filtering
    from yt_network_scraper import filter_comments, CommentFilter
    filtered = filter_comments(result, keyword="great", min_likes=10)

    # Video file download
    with YouTubeScraper() as scraper:
        result = scraper.download_video_file("URL", "./video.mp4", quality="720p")

    # Video player with playlist
    from yt_network_scraper import VideoPlayer, Playlist, Track
    player = VideoPlayer(dry_run=True)
    playlist = Playlist(name="My Mix")
    playlist.add_track(Track(path="video.mp4"))
    player.play_playlist(playlist)

    # Pipeline (scrape → filter → sentiment → export → download)
    from yt_network_scraper import ScrapePipeline
    pipeline = ScrapePipeline(
        stages=["scrape", "sentiment", "export"],
        export_format="csv",
        output_dir="./output",
    )
    result = pipeline.run(["URL1", "URL2"])
"""

from __future__ import annotations

from .client import ScraperConfig, YouTubeScraper
from .exceptions import (
    AccessBlockedException,
    BrowserNotInitializedError,
    InvalidVideoURLError,
    ScraperError,
    SeleniumNotInstalledError,
    TranscriptUnavailableError,
)
from .export import (
    batch_comments_to_csv,
    batch_to_csv,
    batch_to_jsonl,
    batch_to_xlsx,
    comments_to_csv,
    download_batch,
    download_video,
    export_batch,
    export_video,
    transcript_to_srt,
    transcript_to_txt,
    video_to_csv,
    video_to_jsonl,
    video_to_xlsx,
)
from .downloader import (
    download_stream,
    download_video as download_video_file,
    extract_streams,
    has_ffmpeg,
    merge_audio_video,
    select_best_audio,
    select_best_progressive,
    select_best_video,
    select_by_quality,
    select_worst_progressive,
)
from .filters import CommentFilter, filter_comments, search_comments, top_comments
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
from .performance import (
    BackoffStrategy,
    LRUCache,
    RateLimiter,
    chunk_list,
    clear_all_caches,
    get_metadata_cache,
    get_stream_cache,
    retry_with_backoff,
)
from .pipeline import (
    PipelineResult,
    PipelineStageResult,
    ScrapePipeline,
    VALID_STAGES,
)
from .player import (
    Playlist,
    Track,
    VideoPlayer,
    create_playlist_from_directory,
    find_player_backend,
    has_ffplay,
    load_playlist,
    save_playlist,
)
from .sentiment import (
    CommentSentiment,
    SentimentResult,
    VideoSentiment,
    analyze_comment_sentiment,
    analyze_sentiment,
    analyze_video_sentiment,
)

__all__ = [
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
]

__version__ = "3.1.0"
