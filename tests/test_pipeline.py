"""Tests for the pipeline module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from media_data_extractor.models import (
    AccessStatus,
    BatchError,
    BatchResult,
    Comment,
    Engagement,
    NetworkInfo,
    Summary,
    Transcript,
    VideoMetadata,
    VideoResult,
)
from media_data_extractor.pipeline import (
    PipelineResult,
    PipelineStageResult,
    ScrapePipeline,
    VALID_STAGES,
)


def _make_video(video_id: str = "vid1") -> VideoResult:
    return VideoResult(
        video_id=video_id,
        source_url=f"https://www.youtube.com/watch?v={video_id}",
        metadata=VideoMetadata(
            video_url=f"https://www.youtube.com/watch?v={video_id}",
            title="Test Video",
            channel_name="TestChannel",
        ),
        engagement=Engagement(comment_count_scraped=2),
        transcript=Transcript(available=False),
        summary=Summary(available=False, text=""),
        comments=[
            Comment(comment_id="c1", likes=5, reply_count=0, is_pinned=False, is_hearted=False, author="A", text="Great!"),
            Comment(comment_id="c2", likes=1, reply_count=0, is_pinned=False, is_hearted=False, author="B", text="Bad"),
        ],
        network=NetworkInfo(access_status=AccessStatus(blocked=False)),
    )


def _make_batch(n: int = 2) -> BatchResult:
    results = [_make_video(f"vid{i}") for i in range(n)]
    return BatchResult(total=n, succeeded=n, failed=0, results=results)


class TestPipelineStages:
    def test_valid_stages(self):
        assert "scrape" in VALID_STAGES
        assert "filter" in VALID_STAGES
        assert "sentiment" in VALID_STAGES
        assert "export" in VALID_STAGES
        assert "download" in VALID_STAGES
        assert "download_video" in VALID_STAGES

    def test_invalid_stage_raises(self):
        with pytest.raises(ValueError, match="Invalid pipeline stages"):
            ScrapePipeline(stages=["invalid_stage"])

    def test_default_stages(self):
        pipeline = ScrapePipeline()
        assert "scrape" in pipeline.stages
        assert "sentiment" in pipeline.stages


class TestPipelineRun:
    @patch("media_data_extractor.pipeline.YouTubeScraper")
    def test_scrape_only(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        pipeline = ScrapePipeline(stages=["scrape"])
        result = pipeline.run(["vid1", "vid2"])

        assert result.total == 2
        assert result.succeeded == 2
        assert len(result.stage_results) == 1
        assert result.stage_results[0].name == "scrape"

    @patch("media_data_extractor.pipeline.YouTubeScraper")
    def test_scrape_and_sentiment(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        pipeline = ScrapePipeline(stages=["scrape", "sentiment"])
        result = pipeline.run(["vid1", "vid2"])

        assert len(result.stage_results) == 2
        assert result.stage_results[1].name == "sentiment"
        assert result.stage_results[1].succeeded == 2
        assert len(result.sentiments) == 2

    @patch("media_data_extractor.pipeline.YouTubeScraper")
    def test_scrape_sentiment_export(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        pipeline = ScrapePipeline(
            stages=["scrape", "sentiment", "export"],
            export_format="json",
            output_dir=str(tmp_path),
        )
        result = pipeline.run(["vid1", "vid2"])

        assert len(result.stage_results) == 3
        assert result.stage_results[2].name == "export"
        assert len(result.output_files) > 0
        assert Path(result.output_files[0]).exists()

    @patch("media_data_extractor.pipeline.YouTubeScraper")
    def test_scrape_filter_sentiment(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        from media_data_extractor.filters import CommentFilter
        pipeline = ScrapePipeline(
            stages=["scrape", "filter", "sentiment"],
            comment_filter=CommentFilter(keyword="great"),
        )
        result = pipeline.run(["vid1", "vid2"])

        assert len(result.stage_results) == 3
        assert result.stage_results[1].name == "filter"

    @patch("media_data_extractor.pipeline.YouTubeScraper")
    def test_scrape_export_csv(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        pipeline = ScrapePipeline(
            stages=["scrape", "export"],
            export_format="csv",
            output_dir=str(tmp_path),
        )
        result = pipeline.run(["vid1", "vid2"])

        assert len(result.output_files) > 0
        content = Path(result.output_files[0]).read_text()
        assert "video_id" in content

    @patch("media_data_extractor.pipeline.YouTubeScraper")
    def test_scrape_export_jsonl(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        pipeline = ScrapePipeline(
            stages=["scrape", "export"],
            export_format="jsonl",
            output_dir=str(tmp_path),
        )
        result = pipeline.run(["vid1", "vid2"])

        content = Path(result.output_files[0]).read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2  # 2 videos

    @patch("media_data_extractor.pipeline.YouTubeScraper")
    def test_scrape_export_xlsx(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        pipeline = ScrapePipeline(
            stages=["scrape", "export"],
            export_format="xlsx",
            output_dir=str(tmp_path),
        )
        result = pipeline.run(["vid1", "vid2"])

        content = Path(result.output_files[0]).read_text()
        assert "<Workbook" in content

    @patch("media_data_extractor.pipeline.YouTubeScraper")
    def test_download_stage(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        pipeline = ScrapePipeline(
            stages=["scrape", "download"],
            download_dir=str(tmp_path / "downloads"),
        )
        result = pipeline.run(["vid1", "vid2"])

        assert len(result.stage_results) == 2
        assert result.stage_results[1].name == "download"
        assert len(result.output_files) > 0

    @patch("media_data_extractor.pipeline.YouTubeScraper")
    def test_empty_urls(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=BatchResult(total=0))
        mock_scraper_class.return_value = mock_scraper

        pipeline = ScrapePipeline(stages=["scrape"])
        result = pipeline.run([])

        assert result.total == 0
        assert result.succeeded == 0

    @patch("media_data_extractor.pipeline.YouTubeScraper")
    def test_scrape_failure(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(side_effect=Exception("Browser error"))
        mock_scraper_class.return_value = mock_scraper

        pipeline = ScrapePipeline(stages=["scrape"])
        result = pipeline.run(["vid1"])

        assert result.failed == 1
        assert result.stage_results[0].error is not None

    def test_result_to_dict(self):
        result = PipelineResult(total=5, succeeded=3, failed=2)
        result.stage_results.append(PipelineStageResult(name="scrape", succeeded=3))
        d = result.to_dict()
        assert d["total"] == 5
        assert d["succeeded"] == 3
        assert d["failed"] == 2
        assert len(d["stage_results"]) == 1

    def test_stage_result_to_dict(self):
        sr = PipelineStageResult(name="scrape", succeeded=5, failed=2, elapsed_seconds=10.5)
        d = sr.to_dict()
        assert d["name"] == "scrape"
        assert d["succeeded"] == 5
        assert d["failed"] == 2
        assert d["elapsed_seconds"] == 10.5
