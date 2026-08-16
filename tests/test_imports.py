"""Tests for package imports and public API surface."""

from __future__ import annotations

import yt_network_scraper
from yt_network_scraper import (
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
)


def test_version():
    assert hasattr(yt_network_scraper, "__version__")
    assert yt_network_scraper.__version__ == "1.0.0"


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
    }
    assert set(yt_network_scraper.__all__) == expected


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
