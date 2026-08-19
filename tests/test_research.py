"""Tests for the research data preparation module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from media_data_extractor.models import (
    AccessStatus,
    BatchResult,
    Comment,
    Engagement,
    NetworkInfo,
    Summary,
    Transcript,
    TranscriptSegment,
    VideoMetadata,
    VideoResult,
)
from media_data_extractor.research import (
    DatasetSummary,
    _sentiment_to_row,
    _sentiment_to_row_empty,
    _video_to_research_row,
    batch_to_dataframe,
    collect_comment_corpus,
    collect_comparison_table,
    collect_dataset,
    collect_transcript_corpus,
    comments_to_dataframe,
    quick_scrape,
    to_dataframe,
)


def _make_video(video_id: str = "vid1") -> VideoResult:
    return VideoResult(
        video_id=video_id,
        source_url=f"https://www.youtube.com/watch?v={video_id}",
        metadata=VideoMetadata(
            video_url=f"https://www.youtube.com/watch?v={video_id}",
            title="Test Video",
            description="A test description",
            views=100000,
            channel_name="TestChannel",
            channel_id="UC123",
            upload_date="2024-01-15",
            duration_seconds=300,
            category="Education",
            is_live=False,
            keywords=["python", "tutorial"],
        ),
        engagement=Engagement(
            likes=5000,
            views=100000,
            comment_count=200,
            comment_count_scraped=3,
        ),
        transcript=Transcript(
            available=True,
            text="Hello world this is a test transcript",
            language="en",
            segments=[
                TranscriptSegment(text="Hello world", start_ms=0, duration_ms=2000),
                TranscriptSegment(text="this is a test", start_ms=2000, duration_ms=3000),
            ],
        ),
        summary=Summary(available=True, text="A test summary"),
        comments=[
            Comment(comment_id="c1", likes=50, reply_count=2, is_pinned=True, is_hearted=False,
                    author="Alice", text="This is amazing and wonderful!"),
            Comment(comment_id="c2", likes=5, reply_count=0, is_pinned=False, is_hearted=True,
                    author="Bob", text="This is terrible and boring"),
            Comment(comment_id="c3", likes=10, reply_count=1, is_pinned=False, is_hearted=False,
                    author="Charlie", text="Okay video, nothing special"),
        ],
        network=NetworkInfo(access_status=AccessStatus(blocked=False)),
    )


def _make_batch(n: int = 2) -> BatchResult:
    results = [_make_video(f"vid{i}") for i in range(n)]
    return BatchResult(total=n, succeeded=n, failed=0, results=results)


# ---------------------------------------------------------------------------
# Test _video_to_research_row
# ---------------------------------------------------------------------------

class TestVideoToResearchRow:
    def test_basic_conversion(self):
        result = _make_video("test1")
        row = _video_to_research_row(result)
        assert row["video_id"] == "test1"
        assert row["title"] == "Test Video"
        assert row["views"] == 100000
        assert row["likes"] == 5000
        assert row["channel_name"] == "TestChannel"

    def test_transcript_truncated(self):
        result = _make_video()
        result.transcript.text = "x" * 5000
        row = _video_to_research_row(result)
        assert len(row["transcript_text"]) <= 1000

    def test_description_truncated(self):
        result = _make_video()
        result.metadata.description = "x" * 2000
        row = _video_to_research_row(result)
        assert len(row["description"]) <= 500

    def test_keywords_joined(self):
        result = _make_video()
        row = _video_to_research_row(result)
        assert row["keywords"] == "python|tutorial"

    def test_empty_fields_handled(self):
        result = _make_video()
        result.metadata.title = None
        result.metadata.views = None
        row = _video_to_research_row(result)
        assert row["title"] == ""
        assert row["views"] == 0


# ---------------------------------------------------------------------------
# Test collect_dataset
# ---------------------------------------------------------------------------

class TestCollectDataset:
    @patch("media_data_extractor.research.YouTubeScraper")
    def test_basic_collection(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        rows, summary = collect_dataset(
            urls=["vid1", "vid2"],
            output_path=str(tmp_path / "dataset.csv"),
        )

        assert len(rows) == 2
        assert summary.succeeded == 2
        assert summary.total_videos == 2
        assert (tmp_path / "dataset.csv").exists()

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_with_sentiment(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        rows, summary = collect_dataset(
            urls=["vid1", "vid2"],
            include_sentiment=True,
        )

        assert "sentiment_label" in rows[0]
        assert "sentiment_positive_pct" in rows[0]
        assert summary.sentiment_available == 2

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_with_comments_export(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        _, summary = collect_dataset(
            urls=["vid1", "vid2"],
            output_path=str(tmp_path / "dataset.csv"),
            include_comments=True,
        )

        assert (tmp_path / "dataset_comments.csv").exists()
        assert len(summary.output_files) >= 2

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_with_transcripts_export(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        _, summary = collect_dataset(
            urls=["vid1", "vid2"],
            output_path=str(tmp_path / "dataset.csv"),
            include_transcripts=True,
        )

        assert (tmp_path / "dataset_transcripts.txt").exists()

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_jsonl_output(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        rows, _ = collect_dataset(
            urls=["vid1", "vid2"],
            output_path=str(tmp_path / "dataset.jsonl"),
            output_format="jsonl",
        )

        content = (tmp_path / "dataset.jsonl").read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2
        json.loads(lines[0])  # Valid JSON

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_json_output(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        collect_dataset(
            urls=["vid1", "vid2"],
            output_path=str(tmp_path / "dataset.json"),
            output_format="json",
        )

        data = json.loads((tmp_path / "dataset.json").read_text())
        assert len(data) == 2

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_empty_urls(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=BatchResult(total=0))
        mock_scraper_class.return_value = mock_scraper

        rows, summary = collect_dataset(urls=[])
        assert rows == []
        assert summary.total_videos == 0


# ---------------------------------------------------------------------------
# Test collect_comment_corpus
# ---------------------------------------------------------------------------

class TestCollectCommentCorpus:
    @patch("media_data_extractor.research.YouTubeScraper")
    def test_basic_collection(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        comments, summary = collect_comment_corpus(urls=["vid1", "vid2"])

        assert len(comments) == 6  # 3 comments × 2 videos
        assert summary.total_comments == 6
        assert "video_id" in comments[0]
        assert "text" in comments[0]

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_with_sentiment(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(1))
        mock_scraper_class.return_value = mock_scraper

        comments, _ = collect_comment_corpus(
            urls=["vid1"],
            include_sentiment=True,
        )

        assert "sentiment_label" in comments[0]
        assert "sentiment_compound" in comments[0]

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_csv_output(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        _, summary = collect_comment_corpus(
            urls=["vid1", "vid2"],
            output_path=str(tmp_path / "comments.csv"),
        )

        content = (tmp_path / "comments.csv").read_text()
        assert "video_id" in content
        assert "Alice" in content
        assert summary.total_comments == 6


# ---------------------------------------------------------------------------
# Test collect_transcript_corpus
# ---------------------------------------------------------------------------

class TestCollectTranscriptCorpus:
    @patch("media_data_extractor.research.YouTubeScraper")
    def test_basic_collection(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        transcripts, summary = collect_transcript_corpus(urls=["vid1", "vid2"])

        assert len(transcripts) == 2
        assert summary.total_transcripts == 2
        assert "transcript" in transcripts[0]
        assert "segments" in transcripts[0]

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_with_metadata(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(1))
        mock_scraper_class.return_value = mock_scraper

        transcripts, _ = collect_transcript_corpus(
            urls=["vid1"],
            include_metadata=True,
        )

        assert "title" in transcripts[0]
        assert "channel" in transcripts[0]
        assert "duration_seconds" in transcripts[0]

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_jsonl_output(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        collect_transcript_corpus(
            urls=["vid1", "vid2"],
            output_path=str(tmp_path / "transcripts.jsonl"),
            output_format="jsonl",
        )

        content = (tmp_path / "transcripts.jsonl").read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_txt_output(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(1))
        mock_scraper_class.return_value = mock_scraper

        collect_transcript_corpus(
            urls=["vid1"],
            output_path=str(tmp_path / "transcripts.txt"),
            output_format="txt",
        )

        content = (tmp_path / "transcripts.txt").read_text()
        assert "vid0" in content or "Hello world" in content


# ---------------------------------------------------------------------------
# Test collect_comparison_table
# ---------------------------------------------------------------------------

class TestCollectComparisonTable:
    @patch("media_data_extractor.research.YouTubeScraper")
    def test_basic_comparison(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(3))
        mock_scraper_class.return_value = mock_scraper

        rows, summary = collect_comparison_table(urls=["vid1", "vid2", "vid3"])

        assert len(rows) == 3
        assert "like_rate" in rows[0]
        assert "comment_rate" in rows[0]
        assert "engagement_rate" in rows[0]

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_sorted_by_views(self, mock_scraper_class):
        batch = _make_batch(3)
        batch.results[0].metadata.views = 100
        batch.results[1].metadata.views = 500
        batch.results[2].metadata.views = 300

        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=batch)
        mock_scraper_class.return_value = mock_scraper

        rows, _ = collect_comparison_table(urls=["vid1", "vid2", "vid3"])

        assert rows[0]["views"] >= rows[1]["views"] >= rows[2]["views"]

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_with_sentiment(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        rows, summary = collect_comparison_table(
            urls=["vid1", "vid2"],
            include_sentiment=True,
        )

        assert "sentiment_label" in rows[0]
        assert "sentiment_avg_compound" in rows[0]
        assert summary.sentiment_available == 2

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_csv_output(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(2))
        mock_scraper_class.return_value = mock_scraper

        _, summary = collect_comparison_table(
            urls=["vid1", "vid2"],
            output_path=str(tmp_path / "comparison.csv"),
        )

        content = (tmp_path / "comparison.csv").read_text()
        assert "engagement_rate" in content
        assert "like_rate" in content

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_engagement_rate_calculation(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.batch_scrape = MagicMock(return_value=_make_batch(1))
        mock_scraper_class.return_value = mock_scraper

        rows, _ = collect_comparison_table(urls=["vid1"])

        # likes=5000, comments=200, views=100000
        # engagement_rate = (5000 + 200) / 100000 = 0.052
        assert abs(rows[0]["engagement_rate"] - 0.052) < 0.001
        # like_rate = 5000 / 100000 = 0.05
        assert abs(rows[0]["like_rate"] - 0.05) < 0.001


# ---------------------------------------------------------------------------
# Test quick_scrape
# ---------------------------------------------------------------------------

class TestQuickScrape:
    @patch("media_data_extractor.research.YouTubeScraper")
    def test_basic_quick_scrape(self, mock_scraper_class):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.get_video = MagicMock(return_value=_make_video("test1"))
        mock_scraper_class.return_value = mock_scraper

        data = quick_scrape("test1")

        assert data["video_id"] == "test1"
        assert data["title"] == "Test Video"
        assert data["views"] == 100000
        assert "sentiment_label" in data

    @patch("media_data_extractor.research.YouTubeScraper")
    def test_with_output_files(self, mock_scraper_class, tmp_path):
        mock_scraper = MagicMock()
        mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
        mock_scraper.__exit__ = MagicMock(return_value=None)
        mock_scraper.get_video = MagicMock(return_value=_make_video("test1"))
        mock_scraper_class.return_value = mock_scraper

        quick_scrape(
            "test1",
            output_dir=str(tmp_path),
            formats=("json", "csv", "txt"),
        )

        assert (tmp_path / "test1.json").exists()
        assert (tmp_path / "test1.csv").exists()
        assert (tmp_path / "test1_transcript.txt").exists()


# ---------------------------------------------------------------------------
# Test pandas integration
# ---------------------------------------------------------------------------

class TestPandasIntegration:
    def test_to_dataframe(self):
        pytest.importorskip("pandas")
        rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        df = to_dataframe(rows)
        assert len(df) == 2
        assert list(df.columns) == ["a", "b"]

    def test_to_dataframe_no_pandas(self):
        rows = [{"a": 1}]
        with patch.dict("sys.modules", {"pandas": None}):
            with pytest.raises(ImportError, match="pandas is required"):
                to_dataframe(rows)

    def test_batch_to_dataframe(self):
        pytest.importorskip("pandas")
        batch = _make_batch(2)
        df = batch_to_dataframe(batch)
        assert len(df) == 2
        assert "video_id" in df.columns

    def test_batch_to_dataframe_with_sentiment(self):
        pytest.importorskip("pandas")
        batch = _make_batch(2)
        df = batch_to_dataframe(batch, include_sentiment=True)
        assert "sentiment_label" in df.columns

    def test_comments_to_dataframe(self):
        pytest.importorskip("pandas")
        results = [_make_video("v1"), _make_video("v2")]
        df = comments_to_dataframe(results)
        assert len(df) == 6  # 3 comments × 2 videos
        assert "text" in df.columns

    def test_comments_to_dataframe_with_sentiment(self):
        pytest.importorskip("pandas")
        results = [_make_video("v1")]
        df = comments_to_dataframe(results, include_sentiment=True)
        assert "sentiment_label" in df.columns


# ---------------------------------------------------------------------------
# Test DatasetSummary
# ---------------------------------------------------------------------------

class TestDatasetSummary:
    def test_to_dict(self):
        s = DatasetSummary(total_videos=10, succeeded=8, failed=2, total_comments=200)
        d = s.to_dict()
        assert d["total_videos"] == 10
        assert d["succeeded"] == 8
        assert d["total_comments"] == 200

    def test_str(self):
        s = DatasetSummary(total_videos=5, succeeded=3, failed=2, total_comments=50)
        text = str(s)
        assert "3/5" in text
        assert "50" in text


# ---------------------------------------------------------------------------
# Test sentiment helpers
# ---------------------------------------------------------------------------

class TestSentimentHelpers:
    def test_sentiment_to_row(self):
        from media_data_extractor.sentiment import VideoSentiment
        sentiment = VideoSentiment(
            video_id="v1",
            total_comments=10,
            positive_count=5,
            negative_count=3,
            neutral_count=2,
            average_compound=0.3,
            overall_label="positive",
        )
        row = _sentiment_to_row(sentiment)
        assert row["sentiment_label"] == "positive"
        assert row["sentiment_positive_count"] == 5
        assert row["sentiment_avg_compound"] == 0.3

    def test_sentiment_to_row_empty(self):
        row = _sentiment_to_row_empty()
        assert row["sentiment_label"] == "unknown"
        assert row["sentiment_positive_count"] == 0
        assert row["sentiment_avg_compound"] == 0
