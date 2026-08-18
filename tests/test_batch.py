"""Tests for batch scraping functionality in media_data_extractor.client.

All browser and HTTP calls are mocked — no live requests.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from media_data_extractor.client import ScraperConfig, YouTubeScraper
from media_data_extractor.exceptions import InvalidVideoURLError
from media_data_extractor.models import (
    BatchResult,
    BatchError,
    VideoResult,
    VideoMetadata,
    Engagement,
    Transcript,
    Summary,
    NetworkInfo,
    AccessStatus,
)


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


# ---------------------------------------------------------------------------
# Checkpoint functionality
# ---------------------------------------------------------------------------

class TestCheckpoint:
    def _make_mock_result(self, video_id: str) -> VideoResult:
        return VideoResult(
            video_id=video_id,
            source_url=f"https://www.youtube.com/watch?v={video_id}",
            metadata=VideoMetadata(video_url=f"https://www.youtube.com/watch?v={video_id}", title=f"Test {video_id}"),
            engagement=Engagement(comment_count_scraped=0),
            transcript=Transcript(available=False),
            summary=Summary(available=False, text=""),
            comments=[],
            network=NetworkInfo(access_status=AccessStatus(blocked=False)),
        )

    def test_checkpoint_creates_file(self, tmp_path):
        """Checkpoint file is created with completed results."""
        checkpoint_path = str(tmp_path / "checkpoint.json")
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)
        mock_result = self._make_mock_result("vid1")

        with patch.object(YouTubeScraper, "get_video", return_value=mock_result):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(["vid1"], checkpoint=checkpoint_path)

        import os
        assert os.path.exists(checkpoint_path)
        cp_data = json.loads(open(checkpoint_path).read())
        assert "vid1" in cp_data
        assert cp_data["vid1"]["status"] == "ok"

    def test_checkpoint_skips_completed(self, tmp_path):
        """Already-completed videos are skipped on re-run."""
        checkpoint_path = str(tmp_path / "checkpoint.json")
        # Pre-create checkpoint with vid1 already done (proper result dict)
        mock_result = self._make_mock_result("vid1")
        cp_data = {"vid1": {"status": "ok", "result": mock_result.to_dict()}}
        with open(checkpoint_path, "w") as f:
            json.dump(cp_data, f)

        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        # get_video should NOT be called for vid1
        call_count = 0
        def fake_get_video(url_or_id):
            nonlocal call_count
            call_count += 1
            return self._make_mock_result(url_or_id)

        with patch.object(YouTubeScraper, "get_video", side_effect=fake_get_video):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(["vid1", "vid2"], checkpoint=checkpoint_path)

        # Only vid2 should have been scraped (vid1 was in checkpoint)
        assert call_count == 1
        assert batch.total == 2
        assert batch.succeeded >= 1

    def test_checkpoint_saves_errors(self, tmp_path):
        """Failed videos are also saved to checkpoint."""
        checkpoint_path = str(tmp_path / "checkpoint.json")
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        def fake_get_video(url_or_id):
            raise InvalidVideoURLError(f"Invalid: {url_or_id}")

        with patch.object(YouTubeScraper, "get_video", side_effect=fake_get_video):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(["bad1"], checkpoint=checkpoint_path)

        import os
        assert os.path.exists(checkpoint_path)
        cp_data = json.loads(open(checkpoint_path).read())
        assert "bad1" in cp_data
        assert cp_data["bad1"]["status"] == "error"
        assert cp_data["bad1"]["error_type"] == "InvalidVideoURLError"

    def test_checkpoint_no_file(self):
        """Batch works fine without checkpoint."""
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)
        mock_result = self._make_mock_result("vid1")

        with patch.object(YouTubeScraper, "get_video", return_value=mock_result):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(["vid1"])

        assert batch.succeeded == 1


# ---------------------------------------------------------------------------
# Resilient batch scraping (auto-retry on crash)
# ---------------------------------------------------------------------------

class TestBatchScrapeResilient:
    def _make_mock_result(self, video_id: str) -> VideoResult:
        return VideoResult(
            video_id=video_id,
            source_url=f"https://www.youtube.com/watch?v={video_id}",
            metadata=VideoMetadata(video_url=f"https://www.youtube.com/watch?v={video_id}", title=f"Test {video_id}"),
            engagement=Engagement(comment_count_scraped=0),
            transcript=Transcript(available=False),
            summary=Summary(available=False, text=""),
            comments=[],
            network=NetworkInfo(access_status=AccessStatus(blocked=False)),
        )

    def test_resilient_requires_checkpoint(self):
        """batch_scrape_resilient raises ValueError without checkpoint."""
        scraper = YouTubeScraper()
        with pytest.raises(ValueError, match="checkpoint"):
            scraper.batch_scrape_resilient(["vid1"])

    def test_resilient_no_crash(self, tmp_path):
        """Resilient batch completes normally when no crash occurs."""
        checkpoint_path = str(tmp_path / "cp.json")
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        mock_result = self._make_mock_result("vid1")

        with patch.object(YouTubeScraper, "get_video", return_value=mock_result):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape_resilient(
                        ["vid1"], checkpoint=checkpoint_path, max_retries=3, retry_delay=0
                    )

        assert batch.total == 1
        assert batch.succeeded == 1
        assert batch.failed == 0

    def test_resilient_crash_then_recover(self, tmp_path):
        """Resilient batch crashes on first attempt, succeeds on retry."""
        checkpoint_path = str(tmp_path / "cp.json")
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        # Pre-create checkpoint with vid1 done
        cp_data = {"vid1": {"status": "ok", "result": self._make_mock_result("vid1").to_dict()}}
        with open(checkpoint_path, "w") as f:
            json.dump(cp_data, f)

        mock_result2 = self._make_mock_result("vid2")

        batch_call_count = 0
        original_batch = YouTubeScraper.batch_scrape

        def patched_batch(self_inner, urls, **kwargs):
            nonlocal batch_call_count
            batch_call_count += 1
            if batch_call_count == 1:
                raise RuntimeError("Batch crashed!")
            return original_batch(self_inner, urls, **kwargs)

        with patch.object(YouTubeScraper, "batch_scrape", patched_batch):
            with patch.object(YouTubeScraper, "get_video", return_value=mock_result2):
                with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                    with patch.object(YouTubeScraper, "__exit__", return_value=None):
                        batch = scraper.batch_scrape_resilient(
                            ["vid1", "vid2"], checkpoint=checkpoint_path, max_retries=3, retry_delay=0
                        )

        assert batch.total == 2
        assert batch.succeeded == 2  # vid1 from checkpoint + vid2 scraped
        assert batch.failed == 0

    def test_resilient_keyboard_interrupt(self, tmp_path):
        """Resilient batch handles KeyboardInterrupt and retries."""
        checkpoint_path = str(tmp_path / "cp.json")
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        # Pre-create checkpoint with vid1 done
        cp_data = {"vid1": {"status": "ok", "result": self._make_mock_result("vid1").to_dict()}}
        with open(checkpoint_path, "w") as f:
            json.dump(cp_data, f)

        mock_result2 = self._make_mock_result("vid2")

        batch_call_count = 0
        original_batch = YouTubeScraper.batch_scrape

        def patched_batch(self_inner, urls, **kwargs):
            nonlocal batch_call_count
            batch_call_count += 1
            if batch_call_count == 1:
                raise KeyboardInterrupt("Ctrl+C!")
            return original_batch(self_inner, urls, **kwargs)

        with patch.object(YouTubeScraper, "batch_scrape", patched_batch):
            with patch.object(YouTubeScraper, "get_video", return_value=mock_result2):
                with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                    with patch.object(YouTubeScraper, "__exit__", return_value=None):
                        batch = scraper.batch_scrape_resilient(
                            ["vid1", "vid2"], checkpoint=checkpoint_path, max_retries=3, retry_delay=0
                        )

        assert batch.total == 2
        assert batch.succeeded == 2

    def test_resilient_max_retries_exhausted(self, tmp_path):
        """Resilient batch stops after max_retries and returns checkpoint data."""
        checkpoint_path = str(tmp_path / "cp.json")
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        # Pre-create checkpoint with vid1 done
        cp_data = {"vid1": {"status": "ok", "result": self._make_mock_result("vid1").to_dict()}}
        with open(checkpoint_path, "w") as f:
            json.dump(cp_data, f)

        # Always crash
        with patch.object(YouTubeScraper, "batch_scrape", side_effect=RuntimeError("Always crash")):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape_resilient(
                        ["vid1", "vid2"], checkpoint=checkpoint_path, max_retries=2, retry_delay=0
                    )

        # Should still return vid1 from checkpoint
        assert batch.total == 2
        assert batch.succeeded == 1  # vid1 from checkpoint
        assert len(batch.results) == 1

    def test_resilient_all_succeed_no_retry(self, tmp_path):
        """Resilient batch doesn't retry when everything succeeds first time."""
        checkpoint_path = str(tmp_path / "cp.json")
        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        mock_result = self._make_mock_result("vid1")

        batch_call_count = 0
        original_batch = YouTubeScraper.batch_scrape

        def patched_batch(self_inner, urls, **kwargs):
            nonlocal batch_call_count
            batch_call_count += 1
            return original_batch(self_inner, urls, **kwargs)

        with patch.object(YouTubeScraper, "batch_scrape", patched_batch):
            with patch.object(YouTubeScraper, "get_video", return_value=mock_result):
                with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                    with patch.object(YouTubeScraper, "__exit__", return_value=None):
                        batch = scraper.batch_scrape_resilient(
                            ["vid1"], checkpoint=checkpoint_path, max_retries=3, retry_delay=0
                        )

        # Should only call batch_scrape once (no retry needed)
        assert batch_call_count == 1
        assert batch.succeeded == 1


# ---------------------------------------------------------------------------
# retry_failed parameter
# ---------------------------------------------------------------------------

class TestRetryFailed:
    def _make_mock_result(self, video_id: str) -> VideoResult:
        return VideoResult(
            video_id=video_id,
            source_url=f"https://www.youtube.com/watch?v={video_id}",
            metadata=VideoMetadata(video_url=f"https://www.youtube.com/watch?v={video_id}", title=f"Test {video_id}"),
            engagement=Engagement(comment_count_scraped=0),
            transcript=Transcript(available=False),
            summary=Summary(available=False, text=""),
            comments=[],
            network=NetworkInfo(access_status=AccessStatus(blocked=False)),
        )

    def test_retry_failed_retries_errors(self, tmp_path):
        """retry_failed=True retries previously-failed videos."""
        checkpoint_path = str(tmp_path / "cp.json")
        # Pre-create checkpoint: vid1 ok, vid2 error
        cp_data = {
            "vid1": {"status": "ok", "result": self._make_mock_result("vid1").to_dict()},
            "vid2": {"status": "error", "error_type": "RuntimeError", "error_message": "crashed"},
        }
        with open(checkpoint_path, "w") as f:
            json.dump(cp_data, f)

        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        scraped_urls = []
        def fake_get_video(url_or_id):
            scraped_urls.append(url_or_id)
            return self._make_mock_result(url_or_id)

        with patch.object(YouTubeScraper, "get_video", side_effect=fake_get_video):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(
                        ["vid1", "vid2"],
                        checkpoint=checkpoint_path,
                        retry_failed=True,
                    )

        # vid1 should be skipped (ok), vid2 should be retried
        assert scraped_urls == ["vid2"]
        assert batch.succeeded == 2  # vid1 from checkpoint + vid2 scraped

    def test_retry_false_skips_all(self, tmp_path):
        """retry_failed=False (default) skips all checkpointed videos."""
        checkpoint_path = str(tmp_path / "cp.json")
        cp_data = {
            "vid1": {"status": "ok", "result": self._make_mock_result("vid1").to_dict()},
            "vid2": {"status": "error", "error_type": "RuntimeError", "error_message": "crashed"},
        }
        with open(checkpoint_path, "w") as f:
            json.dump(cp_data, f)

        config = ScraperConfig(max_workers=2, batch_delay=0)
        scraper = YouTubeScraper(config)

        scraped_urls = []
        def fake_get_video(url_or_id):
            scraped_urls.append(url_or_id)
            return self._make_mock_result(url_or_id)

        with patch.object(YouTubeScraper, "get_video", side_effect=fake_get_video):
            with patch.object(YouTubeScraper, "__enter__", return_value=scraper):
                with patch.object(YouTubeScraper, "__exit__", return_value=None):
                    batch = scraper.batch_scrape(
                        ["vid1", "vid2"],
                        checkpoint=checkpoint_path,
                        retry_failed=False,
                    )

        # Both should be skipped
        assert scraped_urls == []
        assert batch.succeeded == 1  # only vid1 (ok)
