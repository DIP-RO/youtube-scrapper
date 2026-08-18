"""Tests for batch scraping functionality in yt_network_scraper.client.

All browser and HTTP calls are mocked — no live requests.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from yt_network_scraper.client import ScraperConfig, YouTubeScraper
from yt_network_scraper.exceptions import InvalidVideoURLError
from yt_network_scraper.models import BatchResult, BatchError, VideoResult


# ---------------------------------------------------------------------------
# BatchResult / BatchError models
# ---------------------------------------------------------------------------

class TestBatchModels:
    def test_batch_result_defaults(self):
        br = BatchResult()
        assert br.total == 0
        assert br.succeeded == 0
        assert br.failed == 0
        assert br.results == []
        assert br.errors == []
        assert br.elapsed_seconds == 0.0

    def test_batch_result_to_dict(self):
        br = BatchResult(total=3, succeeded=2, failed=1, elapsed_seconds=5.5)
        d = br.to_dict()
        assert d["total"] == 3
        assert d["succeeded"] == 2
        assert d["failed"] == 1
        assert d["elapsed_seconds"] == 5.5

    def test_batch_error(self):
        err = BatchError(url_or_id="bad_url", error_type="InvalidVideoURLError", error_message="Invalid")
        assert err.url_or_id == "bad_url"
        assert err.error_type == "InvalidVideoURLError"
        assert err.error_message == "Invalid"


# ---------------------------------------------------------------------------
# ScraperConfig batch options
# ---------------------------------------------------------------------------

class TestBatchConfig:
    def test_batch_defaults(self):
        config = ScraperConfig()
        assert config.max_workers == 3
        assert config.batch_delay == 2.0

    def test_batch_custom(self):
        config = ScraperConfig(max_workers=8, batch_delay=0.5)
        assert config.max_workers == 8
        assert config.batch_delay == 0.5


# ---------------------------------------------------------------------------
# batch_scrape with mocked get_video
# ---------------------------------------------------------------------------

class TestBatchScrape:
    def _make_mock_result(self, video_id: str) -> VideoResult:
        """Create a minimal mock VideoResult."""
        return VideoResult(
            video_id=video_id,
            source_url=f"https://www.youtube.com/watch?v={video_id}",
            metadata=MagicMock(),
            engagement=MagicMock(),
            transcript=MagicMock(),
            summary=MagicMock(),
            comments=[],
            network=MagicMock(),
        )

    def test_all_success(self):
        """All videos succeed."""
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        mock_results = {
            "vid1": self._make_mock_result("vid1"),
            "vid2": self._make_mock_result("vid2"),
            "vid3": self._make_mock_result("vid3"),
        }

        def fake_get_video(url_or_id):
            return mock_results[url_or_id]

        with patch.object(YouTubeScraper, "get_video", side_effect=fake_get_video):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(["vid1", "vid2", "vid3"])

        assert batch.total == 3
        assert batch.succeeded == 3
        assert batch.failed == 0
        assert len(batch.results) == 3
        assert len(batch.errors) == 0
        assert batch.elapsed_seconds >= 0

    def test_partial_failure(self):
        """Some videos fail, others succeed."""
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        mock_result = self._make_mock_result("vid1")

        def fake_get_video(url_or_id):
            if url_or_id == "vid1":
                return mock_result
            raise InvalidVideoURLError(f"Invalid: {url_or_id}")

        with patch.object(YouTubeScraper, "get_video", side_effect=fake_get_video):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(["vid1", "bad1", "bad2"])

        assert batch.total == 3
        assert batch.succeeded == 1
        assert batch.failed == 2
        assert len(batch.results) == 1
        assert len(batch.errors) == 2
        assert batch.errors[0].error_type == "InvalidVideoURLError"

    def test_all_fail(self):
        """All videos fail."""
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        def fake_get_video(url_or_id):
            raise InvalidVideoURLError(f"Invalid: {url_or_id}")

        with patch.object(YouTubeScraper, "get_video", side_effect=fake_get_video):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(["bad1", "bad2"])

        assert batch.total == 2
        assert batch.succeeded == 0
        assert batch.failed == 2
        assert len(batch.results) == 0
        assert len(batch.errors) == 2

    def test_empty_list(self):
        """Empty URL list returns empty batch."""
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
            with patch.object(YouTubeScraper, "__exit__", return_value=None):
                batch = scraper.batch_scrape([])

        assert batch.total == 0
        assert batch.succeeded == 0
        assert batch.failed == 0

    def test_progress_callback(self):
        """Progress callback is called for each video."""
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        progress_calls = []

        def progress(idx, total, video_id, status):
            progress_calls.append((idx, total, video_id, status))

        mock_result = self._make_mock_result("vid1")

        with patch.object(YouTubeScraper, "get_video", return_value=mock_result):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(["vid1"], progress_callback=progress)

        assert len(progress_calls) == 1
        assert progress_calls[0][0] == 1  # idx
        assert progress_calls[0][1] == 1  # total
        assert progress_calls[0][2] == "vid1"
        assert progress_calls[0][3] == "ok"

    def test_to_dict_serialization(self):
        """Batch result is JSON serializable."""
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        mock_result = self._make_mock_result("vid1")

        def fake_get_video(url_or_id):
            if url_or_id == "vid1":
                return mock_result
            raise InvalidVideoURLError(f"Invalid: {url_or_id}")

        with patch.object(YouTubeScraper, "get_video", side_effect=fake_get_video):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(["vid1", "bad1"])

        d = batch.to_dict()
        assert d["total"] == 2
        assert d["succeeded"] == 1
        assert d["failed"] == 1
        # Should be JSON serializable
        json_str = json.dumps(d, ensure_ascii=False, default=str)
        assert isinstance(json_str, str)
