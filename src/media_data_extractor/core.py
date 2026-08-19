"""Lightweight core API — scraping only, no optional dependencies.

This module provides the absolute minimum imports for YouTube scraping.
Use it when you want the fastest possible import and don't need
downloads, player, pipeline, sentiment, or research helpers.

Example::

    from media_data_extractor.core import YouTubeScraper, ScraperConfig

    with YouTubeScraper() as scraper:
        result = scraper.get_video("VIDEO_ID")
        print(result.metadata.title)

This imports only: models, exceptions, parsing, utils, scraper, client.
No selenium at import time (loaded lazily in __enter__).
No downloader, export, sentiment, filters, player, pipeline, research.
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
]
