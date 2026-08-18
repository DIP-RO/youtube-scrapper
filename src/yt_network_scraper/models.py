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


@dataclass(slots=True)
class StreamFormat:
    """A single downloadable stream format from YouTube's streamingData.

    Attributes:
        itag: YouTube format code (e.g. 22 for 720p mp4, 137 for 1080p video-only).
        url: Download URL for this stream.
        mime_type: MIME type (e.g. "video/mp4", "audio/mp4").
        quality: Quality label (e.g. "720p", "medium", "audio only").
        quality_label: Human-readable quality (e.g. "720p") or None for audio.
        bitrate: Bitrate in bits per second.
        width: Video width in pixels (None for audio-only).
        height: Video height in pixels (None for audio-only).
        fps: Frames per second (None for audio-only).
        content_length: File size in bytes (if known).
        has_audio: Whether this stream includes audio.
        has_video: Whether this stream includes video.
        format_note: Additional note (e.g. "DASH video", "DASH audio").
    """

    itag: int
    url: str
    mime_type: str = ""
    quality: str = ""
    quality_label: str | None = None
    bitrate: int | None = None
    width: int | None = None
    height: int | None = None
    fps: int | None = None
    content_length: int | None = None
    has_audio: bool = False
    has_video: bool = False
    format_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(asdict(self))


@dataclass(slots=True)
class DownloadResult:
    """Result of downloading a video file.

    Attributes:
        video_id: The YouTube video ID.
        output_path: Path where the file was saved.
        format_itag: The itag of the downloaded format.
        file_size_bytes: Size of the downloaded file in bytes.
        mime_type: MIME type of the downloaded file.
        quality: Quality label of the downloaded stream.
        merged: Whether audio and video were merged with ffmpeg.
        audio_path: Path to the audio file if merged (None otherwise).
        video_path: Path to the video file if merged (None otherwise).
        elapsed_seconds: Download time in seconds.
        error: Error message if the download failed (None on success).
    """

    video_id: str = ""
    output_path: str = ""
    format_itag: int = 0
    file_size_bytes: int = 0
    mime_type: str = ""
    quality: str = ""
    merged: bool = False
    audio_path: str | None = None
    video_path: str | None = None
    elapsed_seconds: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and self.file_size_bytes > 0

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable(asdict(self))


@dataclass(slots=True)
class BatchError:
    """Error for a single failed video in a batch."""

    url_or_id: str
    error_type: str
    error_message: str


@dataclass(slots=True)
class BatchResult:
    """Result of scraping multiple videos concurrently.

    Attributes:
        total: Total number of videos requested.
        succeeded: Number of videos successfully scraped.
        failed: Number of videos that failed.
        results: List of successful VideoResult objects.
        errors: List of BatchError objects for failed videos.
        elapsed_seconds: Total wall-clock time for the batch.
    """

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list[VideoResult] = field(default_factory=list)
    errors: list[BatchError] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the batch result to a plain dict suitable for JSON output."""
        return _to_serializable(asdict(self))


def _to_serializable(obj: Any) -> Any:
    """Recursively convert dataclass-asdict output to JSON-safe types."""
    if isinstance(obj, dict):
        return {key: _to_serializable(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_to_serializable(item) for item in obj]
    return obj
