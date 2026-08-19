"""Analytics — sentiment analysis, comment filtering, research helpers.

Import from here::

    from media_data_extractor.analytics import analyze_sentiment, CommentFilter, collect_dataset
"""

from __future__ import annotations

from .filters import (
    CommentFilter,
    filter_comments,
    search_comments,
    top_comments,
)
from .research import (
    DatasetSummary,
    batch_to_dataframe,
    collect_comment_corpus,
    collect_comparison_table,
    collect_dataset,
    collect_transcript_corpus,
    comments_to_dataframe,
    quick_scrape,
    to_dataframe,
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
