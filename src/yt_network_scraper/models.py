"""Data models for structured scraper results.

All models are dataclasses with ``to_dict()`` for JSON serialization.
Fields are ``Optional`` where YouTube may legitimately omit them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class VideoMetadata:
    """Core metadata about a YouTube video."""

    video_url: str
    title: str | None = None
    description: str | None = None
    views: int | None = None
    channel_name: str | None = None
    channel_id: str | None = None
    channel_url: str | None = None
    channel_subscribers: str | None = None
    upload_date: str | None = None
    publish_date: str | None = None
    timestamp: str | None = None
    duration_seconds: int | None = None
    category: str | None = None
    is_live: bool | None = None
    keywords: list[str] = field(default_factory=list)
    thumbnail: str | None = None


@dataclass(slots=True)
class TranscriptSegment:
    """A single timed segment within a transcript."""

    text: str
    start_ms: int | None = None
    duration_ms: int | None = None
    end_ms: int | None = None
    time: str | None = None


@dataclass(slots=True)
class Transcript:
    """Full transcript / captions for a video."""

    available: bool
    segments: list[TranscriptSegment] = field(default_factory=list)
    text: str = ""
    language: str | None = None
    name: str | None = None
    is_auto_generated: bool | None = None
    source: str | None = None
    error: str | None = None


@dataclass(slots=True)
class Comment:
    """A single YouTube comment."""

    comment_id: str | None
    likes: int
    reply_count: int
    is_pinned: bool
    is_hearted: bool
    author: str | None = None
    author_channel_id: str | None = None
    author_channel_url: str | None = None
    text: str | None = None
    published: str | None = None


@dataclass(slots=True)
class DislikeData:
    """Dislike / rating data from the Return YouTube Dislike API."""

    source: str
    dislikes: int | None = None
    likes: int | None = None
    rating: float | None = None
    view_count: int | None = None


@dataclass(slots=True)
class Engagement:
    """Engagement metrics aggregated from multiple sources."""

    comment_count_scraped: int
    likes: int | None = None
    views: int | None = None
    dislikes: DislikeData | None = None
    comment_count: int | None = None


@dataclass(slots=True)
class Summary:
    """Extractive summary of the transcript or description."""

    available: bool
    text: str
    method: str = "none"


@dataclass(slots=True)
class AccessStatus:
    """Result of checking whether YouTube blocked access."""

    blocked: bool
    reasons: list[str] = field(default_factory=list)
    message: str = "Access looks normal"


@dataclass(slots=True)
class NetworkInfo:
    """Diagnostic information about the network scraping process."""

    access_status: AccessStatus
    api_key_found: bool = False
    captured_event_count: int = 0
    dom_scraping: bool = False
    bot_evasion: bool = False


@dataclass(slots=True)
class VideoResult:
    """Complete result of scraping a single YouTube video."""

    video_id: str
    source_url: str
    metadata: VideoMetadata
    engagement: Engagement
    transcript: Transcript
    summary: Summary
    comments: list[Comment] = field(default_factory=list)
    network: NetworkInfo = field(default_factory=NetworkInfo)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire result to a plain dict suitable for JSON output."""
        return _to_serializable(asdict(self))


def _to_serializable(obj: Any) -> Any:
    """Recursively convert dataclass-asdict output to JSON-safe types."""
    if isinstance(obj, dict):
        return {key: _to_serializable(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_to_serializable(item) for item in obj]
    return obj
