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
    comments_to_csv,
    export_batch,
    export_video,
    transcript_to_txt,
    video_to_csv,
    video_to_jsonl,
)
from .filters import CommentFilter, filter_comments, search_comments, top_comments
from .models import (
    AccessStatus,
    BatchError,
    BatchResult,
    Comment,
    DislikeData,
    Engagement,
    NetworkInfo,
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
    # Export
    "export_video",
    "export_batch",
    "video_to_csv",
    "comments_to_csv",
    "transcript_to_txt",
    "video_to_jsonl",
    "batch_to_csv",
    "batch_to_jsonl",
    "batch_comments_to_csv",
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
