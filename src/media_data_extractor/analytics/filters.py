"""Comment filtering utilities for research workflows.

Filter comments by keyword, author, minimum likes, date range, or
sentiment label. These functions operate on already-scraped VideoResult
objects — no network calls are needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..core.models import Comment, VideoResult
from .sentiment import analyze_comment_sentiment


@dataclass(slots=True)
class CommentFilter:
    """Filter criteria for comments.

    All fields are optional — set only the ones you want to filter by.

    Attributes:
        keyword: Case-insensitive substring to search for in comment text.
        author: Case-insensitive substring to match against author name.
        min_likes: Minimum number of likes a comment must have.
        max_likes: Maximum number of likes a comment must have.
        min_text_length: Minimum length of comment text (filters out short/spam comments).
        date_from: ISO date string (e.g. "2024-01-01") — comments on or after this date.
        date_to: ISO date string (e.g. "2024-12-31") — comments on or before this date.
        sentiment: Filter by sentiment label: "positive", "negative", or "neutral".
        is_reply: If True, only return replies. If False, only top-level comments.
            If None, return all.
        regex: Regular expression pattern to match against comment text.

    Example::

        # Filter for high-quality positive comments
        f = CommentFilter(
            min_likes=10,
            min_text_length=20,
            sentiment="positive",
        )
        filtered = filter_comments(result, filter=f)
    """

    keyword: str | None = None
    author: str | None = None
    min_likes: int | None = None
    max_likes: int | None = None
    min_text_length: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    sentiment: str | None = None
    is_reply: bool | None = None
    regex: str | None = None

    def matches(self, comment: Comment) -> bool:
        """Check if a single comment matches all filter criteria."""
        # Keyword filter (case-insensitive substring)
        if self.keyword:
            if self.keyword.lower() not in (comment.text or "").lower():
                return False

        # Author filter (case-insensitive substring)
        if self.author:
            if self.author.lower() not in (comment.author or "").lower():
                return False

        # Likes range filter
        comment_likes = getattr(comment, "likes", None) or 0
        if self.min_likes is not None and comment_likes < self.min_likes:
            return False
        if self.max_likes is not None and comment_likes > self.max_likes:
            return False

        # Text length filter
        text_len = len(comment.text or "")
        if self.min_text_length is not None and text_len < self.min_text_length:
            return False

        # Date range filter (uses 'published' field)
        comment_date = getattr(comment, "published", None) or ""
        if self.date_from and comment_date < self.date_from:
            return False
        if self.date_to and comment_date > self.date_to:
            return False

        # Regex filter
        if self.regex:
            if not re.search(self.regex, comment.text or "", re.IGNORECASE):
                return False

        # Sentiment filter
        if self.sentiment:
            sentiment_result = analyze_comment_sentiment(comment)
            if sentiment_result.sentiment.label != self.sentiment.lower():
                return False

        return True


def filter_comments(
    result: VideoResult,
    filter: CommentFilter | None = None,
    **kwargs: Any,
) -> list[Comment]:
    """Filter comments from a VideoResult using a CommentFilter.

    Can pass a CommentFilter object or keyword arguments::

        filter_comments(result, keyword="great", min_likes=10)
        filter_comments(result, filter=CommentFilter(author="John"))

    Args:
        result: A VideoResult with comments.
        filter: A CommentFilter object. If None, uses kwargs.
        **kwargs: Used to construct a CommentFilter if filter is None.

    Returns:
        List of comments matching all criteria.
    """
    if filter is None:
        filter = CommentFilter(**kwargs)
    return [c for c in result.comments if filter.matches(c)]


def search_comments(result: VideoResult, keyword: str) -> list[Comment]:
    """Quick helper: search comments for a keyword (case-insensitive)."""
    return filter_comments(result, keyword=keyword)


def top_comments(result: VideoResult, n: int = 10, by: str = "likes") -> list[Comment]:
    """Get the top N comments sorted by likes or text length.

    Args:
        result: A VideoResult with comments.
        n: Number of comments to return.
        by: Sort by "likes" (default) or "length".
    """
    if by == "length":
        sorted_comments = sorted(
            result.comments,
            key=lambda c: len(c.text or ""),
            reverse=True,
        )
    else:
        sorted_comments = sorted(
            result.comments,
            key=lambda c: getattr(c, "likes", None) or 0,
            reverse=True,
        )
    return sorted_comments[:n]
