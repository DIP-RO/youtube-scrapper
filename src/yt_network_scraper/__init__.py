"""yt-network-scraper — A network-first YouTube video scraper.

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
]

__version__ = "1.0.0"
