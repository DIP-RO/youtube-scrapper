"""Tests for the YouTubeScraper client in media_data_extractor.platforms.youtube.scraper.

The Selenium driver and HTTP session are fully mocked — no browser or
live network requests are involved.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from media_data_extractor.platforms.youtube.scraper import ScraperConfig, YouTubeScraper
from media_data_extractor.core.exceptions import (
    BrowserNotInitializedError,
    InvalidVideoURLError,
    SeleniumNotInstalledError,
)
from media_data_extractor.core.models import VideoResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<script>var ytInitialPlayerResponse = {
    "videoDetails": {
        "title": "Test Video",
        "shortDescription": "A great test video about Python.",
        "viewCount": "10000",
        "author": "TestChannel",
        "channelId": "UC_test",
        "lengthSeconds": "300",
        "isLiveContent": false,
        "keywords": ["python", "test"],
        "thumbnail": {"thumbnails": [{"url": "https://example.com/thumb.jpg"}]}
    },
    "microformat": {
        "playerMicroformatRenderer": {
            "uploadDate": "2024-01-01",
            "publishDate": "2024-01-01",
            "category": "Education",
            "ownerProfileUrl": "https://www.youtube.com/channel/UC_test"
        }
    },
    "captions": {
        "playerCaptionsTracklistRenderer": {
            "captionTracks": [
                {"languageCode": "en", "baseUrl": "https://example.com/tt?lang=en", "kind": "asr"}
            ]
        }
    }
};</script>
<script>var ytInitialData = {
    "contents": {
        "videoOwnerRenderer": {
            "title": {"simpleText": "TestChannel"},
            "subscriberCountText": {"simpleText": "1.5M subscribers"}
        }
    },
    "commentsHeaderRenderer": {
        "countText": {"runs": [{"text": "50"}, {"text": " Comments"}]}
    }
};</script>
<script>ytcfg.set({
    "INNERTUBE_API_KEY": "AIzaSyTestKey",
    "INNERTUBE_CONTEXT": {"client": {"clientName": "WEB", "clientVersion": "2.20240601.00.00"}}
});</script>
"""

TRANSCRIPT_RESPONSE = {
    "events": [
        {"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "Hello world"}]},
    ]
}


def _make_mock_driver(html: str = SAMPLE_HTML):
    """Create a mock Selenium driver that returns *html* from network logs."""
    driver = MagicMock()
    # get_log returns performance log entries
    log_entry = {
        "message": json.dumps({
            "message": {
                "method": "Network.responseReceived",
                "params": {
                    "type": "Document",
                    "requestId": "req-1",
                    "response": {"url": "https://www.youtube.com/watch?v=test"},
                },
            }
        })
    }
    driver.get_log.return_value = [log_entry]
    # getResponseBody returns the HTML
    driver.execute_cdp_cmd.return_value = {"body": html}
    # find_elements returns empty (no transcript panel buttons)
    driver.find_elements.return_value = []
    return driver


def _make_mock_session():
    """Create a mock requests.Session for transcript/comment/dislike calls."""
    session = MagicMock(spec=requests.Session)
    # GET for timedtext
    session.get.return_value = MagicMock(
        status_code=200,
        json=lambda: TRANSCRIPT_RESPONSE,
    )
    # POST for comments (innertube next) — return empty
    session.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {},
    )
    return session


# ---------------------------------------------------------------------------
# ScraperConfig
# ---------------------------------------------------------------------------

class TestScraperConfig:
    def test_defaults(self):
        config = ScraperConfig()
        assert config.headless is True
        assert config.timeout == 25
        assert config.max_comments == 25
        assert config.transcript_language == "en"

    def test_custom(self):
        config = ScraperConfig(headless=False, max_comments=100, timeout=60)
        assert config.headless is False
        assert config.max_comments == 100
        assert config.timeout == 60


# ---------------------------------------------------------------------------
# YouTubeScraper initialization
# ---------------------------------------------------------------------------

class TestYouTubeScraperInit:
    def test_default_config(self):
        scraper = YouTubeScraper()
        assert scraper.config.max_comments == 25
        assert scraper.driver is None

    def test_custom_config(self):
        config = ScraperConfig(max_comments=50)
        scraper = YouTubeScraper(config)
        assert scraper.config.max_comments == 50

    def test_session_headers(self):
        scraper = YouTubeScraper()
        assert "User-Agent" in scraper.session.headers
        assert "Accept-Language" in scraper.session.headers


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    @patch("media_data_extractor.platforms.youtube.scraper.YouTubeScraper._build_driver")
    def test_enter_builds_driver(self, mock_build):
        mock_build.return_value = MagicMock()
        scraper = YouTubeScraper()
        with scraper as s:
            assert s is scraper
            assert s.driver is not None
        assert scraper.driver is None

    @patch("media_data_extractor.platforms.youtube.scraper.YouTubeScraper._build_driver")
    def test_exit_quits_driver(self, mock_build):
        mock_driver = MagicMock()
        mock_build.return_value = mock_driver
        scraper = YouTubeScraper()
        with scraper:
            pass
        mock_driver.quit.assert_called_once()
        assert scraper.driver is None


# ---------------------------------------------------------------------------
# get_video — invalid input
# ---------------------------------------------------------------------------

class TestGetVideoInvalidInput:
    def test_invalid_url_raises(self):
        scraper = YouTubeScraper()
        with pytest.raises(InvalidVideoURLError):
            scraper.get_video("https://example.com/page")

    def test_empty_string_raises(self):
        scraper = YouTubeScraper()
        with pytest.raises(InvalidVideoURLError):
            scraper.get_video("")


# ---------------------------------------------------------------------------
# get_video — not in context manager
# ---------------------------------------------------------------------------

class TestGetVideoNoContext:
    def test_raises_browser_not_initialized(self):
        scraper = YouTubeScraper()
        with pytest.raises(BrowserNotInitializedError):
            scraper.get_video("dQw4w9WgXcQ")


# ---------------------------------------------------------------------------
# get_video — Selenium not installed
# ---------------------------------------------------------------------------

class TestSeleniumNotInstalled:
    def test_build_driver_raises(self):
        scraper = YouTubeScraper()
        with patch("builtins.__import__", side_effect=ModuleNotFoundError("No selenium")):
            with pytest.raises(SeleniumNotInstalledError):
                scraper._build_driver()


# ---------------------------------------------------------------------------
# get_video — full flow with mocks
# ---------------------------------------------------------------------------

class TestGetVideoFullFlow:
    @patch("media_data_extractor.platforms.youtube.scraper.YouTubeScraper._build_driver")
    def test_successful_scrape(self, mock_build):
        mock_driver = _make_mock_driver()
        mock_build.return_value = mock_driver

        scraper = YouTubeScraper(ScraperConfig(max_comments=0))
        # Replace the session with a mock
        scraper.session = _make_mock_session()

        with scraper:
            result = scraper.get_video("dQw4w9WgXcQ")

        assert isinstance(result, VideoResult)
        assert result.video_id == "dQw4w9WgXcQ"
        assert result.metadata.title == "Test Video"
        assert result.metadata.views == 10000
        assert result.metadata.channel_name == "TestChannel"
        assert result.metadata.channel_id == "UC_test"
        assert result.metadata.keywords == ["python", "test"]
        assert result.transcript.available is True
        assert "Hello world" in result.transcript.text
        assert result.summary.available is True
        assert result.network.api_key_found is True
        assert result.network.dom_scraping is False
        assert result.network.bot_evasion is False
        assert result.network.access_status.blocked is False

    @patch("media_data_extractor.platforms.youtube.scraper.YouTubeScraper._build_driver")
    def test_to_dict_serializable(self, mock_build):
        mock_driver = _make_mock_driver()
        mock_build.return_value = mock_driver

        scraper = YouTubeScraper(ScraperConfig(max_comments=0))
        scraper.session = _make_mock_session()

        with scraper:
            result = scraper.get_video("dQw4w9WgXcQ")

        d = result.to_dict()
        # Must be JSON-serializable
        json.dumps(d)
        assert d["video_id"] == "dQw4w9WgXcQ"

    @patch("media_data_extractor.platforms.youtube.scraper.YouTubeScraper._build_driver")
    def test_accepts_full_url(self, mock_build):
        mock_driver = _make_mock_driver()
        mock_build.return_value = mock_driver

        scraper = YouTubeScraper(ScraperConfig(max_comments=0))
        scraper.session = _make_mock_session()

        with scraper:
            result = scraper.get_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result.video_id == "dQw4w9WgXcQ"

    @patch("media_data_extractor.platforms.youtube.scraper.YouTubeScraper._build_driver")
    def test_accepts_youtu_be_url(self, mock_build):
        mock_driver = _make_mock_driver()
        mock_build.return_value = mock_driver

        scraper = YouTubeScraper(ScraperConfig(max_comments=0))
        scraper.session = _make_mock_session()

        with scraper:
            result = scraper.get_video("https://youtu.be/dQw4w9WgXcQ")

        assert result.video_id == "dQw4w9WgXcQ"


# ---------------------------------------------------------------------------
# _polite_sleep
# ---------------------------------------------------------------------------

class TestPoliteSleep:
    @patch("media_data_extractor.platforms.youtube.scraper.time.sleep")
    def test_no_sleep_when_delay_zero(self, mock_sleep):
        scraper = YouTubeScraper(ScraperConfig(request_delay=0))
        scraper._polite_sleep()
        mock_sleep.assert_not_called()

    @patch("media_data_extractor.platforms.youtube.scraper.time.sleep")
    def test_sleeps_with_jitter(self, mock_sleep):
        scraper = YouTubeScraper(ScraperConfig(request_delay=1.0))
        scraper._polite_sleep()
        mock_sleep.assert_called_once()
        # The delay should be between (1.0 + 0.25) and (1.0 + 0.9)
        called_delay = mock_sleep.call_args[0][0]
        assert 1.25 <= called_delay <= 1.9
