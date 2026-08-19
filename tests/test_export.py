"""Tests for export functions (CSV, JSONL, TXT)."""

from __future__ import annotations

import csv
import io
import json

import pytest

from media_data_extractor.exporters._all import (
    batch_comments_to_csv,
    batch_to_csv,
    batch_to_jsonl,
    comments_to_csv,
    export_batch,
    export_video,
    transcript_to_txt,
    video_to_csv,
    video_to_jsonl,
)
from media_data_extractor.core.models import (
    AccessStatus,
    BatchError,
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


def _make_video(video_id: str = "vid1") -> VideoResult:
    return VideoResult(
        video_id=video_id,
        source_url=f"https://www.youtube.com/watch?v={video_id}",
        metadata=VideoMetadata(
            video_url=f"https://www.youtube.com/watch?v={video_id}",
            title="Test Video",
            channel_name="TestChannel",
            views=10000,
        ),
        engagement=Engagement(likes=100, comment_count_scraped=2, views=10000),
        transcript=Transcript(
            available=True,
            text="Hello world",
            segments=[TranscriptSegment(text="Hello world", start_ms=0)],
        ),
        summary=Summary(available=True, text="A summary"),
        comments=[
            Comment(comment_id="c1", likes=5, reply_count=0, is_pinned=False, is_hearted=False, author="Alice", text="Great video!"),
            Comment(comment_id="c2", likes=2, reply_count=1, is_pinned=True, is_hearted=False, author="Bob", text="Nice content"),
        ],
        network=NetworkInfo(access_status=AccessStatus(blocked=False)),
    )


class TestVideoToCSV:
    def test_basic_csv(self):
        result = _make_video()
        csv_str = video_to_csv(result)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["video_id"] == "vid1"
        assert rows[0]["title"] == "Test Video"
        assert rows[0]["channel_name"] == "TestChannel"

    def test_csv_has_headers(self):
        result = _make_video()
        csv_str = video_to_csv(result)
        first_line = csv_str.strip().split("\n")[0]
        assert "video_id" in first_line
        assert "title" in first_line
        assert "views" in first_line


class TestCommentsToCSV:
    def test_comments_csv(self):
        result = _make_video()
        csv_str = comments_to_csv(result)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["author"] == "Alice"
        assert rows[0]["text"] == "Great video!"
        assert rows[1]["author"] == "Bob"

    def test_comments_csv_has_video_id(self):
        result = _make_video()
        csv_str = comments_to_csv(result)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert all(r["video_id"] == "vid1" for r in rows)


class TestTranscriptToTXT:
    def test_with_timestamps(self):
        result = _make_video()
        txt = transcript_to_txt(result)
        assert "[00:00] Hello world" in txt

    def test_no_transcript(self):
        result = _make_video()
        result.transcript = Transcript(available=False)
        txt = transcript_to_txt(result)
        assert txt == ""


class TestVideoToJSONL:
    def test_jsonl_is_valid_json(self):
        result = _make_video()
        line = video_to_jsonl(result)
        d = json.loads(line)
        assert d["video_id"] == "vid1"


class TestBatchExport:
    def _make_batch(self) -> BatchResult:
        return BatchResult(
            total=2,
            succeeded=1,
            failed=1,
            results=[_make_video()],
            errors=[BatchError(url_or_id="bad1", error_type="TestError", error_message="Failed")],
        )

    def test_batch_csv(self):
        batch = self._make_batch()
        csv_str = batch_to_csv(batch)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 2  # 1 result + 1 error
        assert rows[0]["video_id"] == "vid1"
        assert "error" in rows[1]["status"]

    def test_batch_jsonl(self):
        batch = self._make_batch()
        lines = batch_to_jsonl(batch).strip().split("\n")
        assert len(lines) == 2
        d1 = json.loads(lines[0])
        assert d1["_status"] == "ok"
        d2 = json.loads(lines[1])
        assert d2["_status"] == "error"

    def test_batch_comments_csv(self):
        batch = self._make_batch()
        csv_str = batch_comments_to_csv(batch)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 2  # 2 comments from 1 video


class TestExportDispatcher:
    def test_export_video_json(self):
        result = _make_video()
        content = export_video(result, format="json")
        d = json.loads(content)
        assert d["video_id"] == "vid1"

    def test_export_video_csv(self):
        result = _make_video()
        content = export_video(result, format="csv")
        assert "video_id" in content

    def test_export_video_csv_comments(self):
        result = _make_video()
        content = export_video(result, format="csv", comments=True)
        assert "author" in content
        assert "Alice" in content

    def test_export_video_txt(self):
        result = _make_video()
        content = export_video(result, format="txt")
        assert "Hello world" in content

    def test_export_video_jsonl(self):
        result = _make_video()
        content = export_video(result, format="jsonl")
        d = json.loads(content)
        assert d["video_id"] == "vid1"

    def test_export_video_invalid_format(self):
        result = _make_video()
        with pytest.raises(ValueError, match="Unknown format"):
            export_video(result, format="xml")

    def test_export_batch_json(self):
        batch = BatchResult(total=1, succeeded=1, results=[_make_video()])
        content = export_batch(batch, format="json")
        d = json.loads(content)
        assert d["succeeded"] == 1

    def test_export_batch_csv(self):
        batch = BatchResult(total=1, succeeded=1, results=[_make_video()])
        content = export_batch(batch, format="csv")
        assert "video_id" in content

    def test_export_batch_invalid_format(self):
        batch = BatchResult()
        with pytest.raises(ValueError, match="Unknown format"):
            export_batch(batch, format="xml")
