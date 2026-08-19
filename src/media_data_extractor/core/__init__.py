"""Core platform-agnostic models, exceptions, and base classes.

This module contains the universal data models and exceptions shared
across all platform implementations (YouTube, TikTok, etc.).

Import from here::

    from media_data_extractor.core import VideoResult, Comment, ScraperError
    # Backward compat: also exports YouTubeScraper
    from media_data_extractor.core import YouTubeScraper, ScraperConfig
"""

from __future__ import annotations

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
# Backward compatibility: re-export YouTubeScraper from core
# (was available in v4.2.0 as from media_data_extractor.core import YouTubeScraper)
from ..platforms.youtube.scraper import ScraperConfig, YouTubeScraper

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
]
