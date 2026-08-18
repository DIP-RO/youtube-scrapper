"""Tests for Excel XML export, SRT format, and download features."""

from __future__ import annotations

import json
import os

import pytest

from yt_network_scraper.export import (
    _ms_to_srt_time,
    _rows_to_xlsx,
    batch_to_xlsx,
    download_batch,
    download_video,
    export_batch,
    export_video,
    transcript_to_srt,
    video_to_xlsx,
)
from yt_network_scraper.models import (
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
            segments=[
                TranscriptSegment(text="Hello world", start_ms=0, duration_ms=2000),
                TranscriptSegment(text="Second line", start_ms=2000, duration_ms=3000),
            ],
        ),
        summary=Summary(available=True, text="A summary"),
        comments=[
            Comment(comment_id="c1", likes=5, reply_count=0, is_pinned=False, is_hearted=False, author="Alice", text="Great video!"),
            Comment(comment_id="c2", likes=2, reply_count=1, is_pinned=True, is_hearted=False, author="Bob", text="Nice content"),
        ],
        network=NetworkInfo(access_status=AccessStatus(blocked=False)),
    )


class TestXlsxExport:
    def test_video_to_xlsx_basic(self):
        result = _make_video()
        xml = video_to_xlsx(result)
        assert "<?xml" in xml
        assert "<Workbook" in xml
        assert "Test Video" in xml
        assert "TestChannel" in xml

    def test_video_to_xlsx_comments(self):
        result = _make_video()
        xml = video_to_xlsx(result, comments=True)
        assert "Alice" in xml
        assert "Great video!" in xml

    def test_batch_to_xlsx(self):
        batch = BatchResult(
            total=1, succeeded=1,
            results=[_make_video()],
        )
        xml = batch_to_xlsx(batch)
        assert "<?xml" in xml
        assert "vid1" in xml

    def test_batch_to_xlsx_comments(self):
        batch = BatchResult(
            total=1, succeeded=1,
            results=[_make_video()],
        )
        xml = batch_to_xlsx(batch, comments=True)
        assert "Alice" in xml
        assert "Bob" in xml

    def test_xlsx_has_headers(self):
        result = _make_video()
        xml = video_to_xlsx(result)
        assert "video_id" in xml
        assert "title" in xml
        assert "channel_name" in xml

    def test_rows_to_xlsx_numbers(self):
        xml = _rows_to_xlsx([[42, "text", 3.14]], ["num", "str", "float"])
        assert 'Type="Number"' in xml
        assert 'Type="String"' in xml

    def test_export_video_xlsx_format(self):
        result = _make_video()
        content = export_video(result, format="xlsx")
        assert "<Workbook" in content

    def test_export_batch_xlsx_format(self):
        batch = BatchResult(total=1, succeeded=1, results=[_make_video()])
        content = export_batch(batch, format="xlsx")
        assert "<Workbook" in content


class TestSrtExport:
    def test_transcript_to_srt_basic(self):
        result = _make_video()
        srt = transcript_to_srt(result)
        assert "1" in srt
        assert "00:00:00,000 --> 00:00:02,000" in srt
        assert "Hello world" in srt
        assert "2" in srt
        assert "00:00:02,000 --> 00:00:05,000" in srt
        assert "Second line" in srt

    def test_transcript_to_srt_no_transcript(self):
        result = _make_video()
        result.transcript = Transcript(available=False)
        srt = transcript_to_srt(result)
        assert srt == ""

    def test_ms_to_srt_time(self):
        assert _ms_to_srt_time(0) == "00:00:00,000"
        assert _ms_to_srt_time(1500) == "00:00:01,500"
        assert _ms_to_srt_time(65000) == "00:01:05,000"
        assert _ms_to_srt_time(3661500) == "01:01:01,500"

    def test_export_video_srt_format(self):
        result = _make_video()
        content = export_video(result, format="srt")
        assert "00:00:00,000" in content


class TestDownloadVideo:
    def test_download_creates_files(self, tmp_path):
        result = _make_video("testvid1")
        files = download_video(result, tmp_path)
        assert len(files) >= 4  # json, csv, txt, srt
        file_names = [f.name for f in files]
        assert "testvid1_result.json" in file_names
        assert "testvid1_metadata.csv" in file_names
        assert "testvid1_comments.csv" in file_names
        assert "testvid1_transcript.txt" in file_names
        assert "testvid1_transcript.srt" in file_names

    def test_download_creates_directory(self, tmp_path):
        result = _make_video()
        new_dir = tmp_path / "output" / "subdir"
        files = download_video(result, new_dir)
        assert new_dir.exists()
        assert len(files) > 0

    def test_download_json_content(self, tmp_path):
        result = _make_video("dlvid")
        files = download_video(result, tmp_path, formats=["json"])
        json_file = [f for f in files if f.suffix == ".json"][0]
        data = json.loads(json_file.read_text(encoding="utf-8"))
        assert data["video_id"] == "dlvid"

    def test_download_csv_content(self, tmp_path):
        result = _make_video("dlvid")
        files = download_video(result, tmp_path, formats=["csv"])
        csv_files = [f for f in files if f.suffix == ".csv"]
        assert len(csv_files) == 2  # metadata + comments
        metadata_csv = [f for f in csv_files if "metadata" in f.name][0]
        content = metadata_csv.read_text(encoding="utf-8")
        assert "video_id" in content
        assert "dlvid" in content

    def test_download_srt_content(self, tmp_path):
        result = _make_video("dlvid")
        files = download_video(result, tmp_path, formats=["srt"])
        srt_file = [f for f in files if f.suffix == ".srt"][0]
        content = srt_file.read_text(encoding="utf-8")
        assert "00:00:00,000" in content

    def test_download_no_transcript(self, tmp_path):
        result = _make_video()
        result.transcript = Transcript(available=False)
        files = download_video(result, tmp_path)
        # Should not have transcript files
        file_names = [f.name for f in files]
        assert not any("transcript" in n for n in file_names)

    def test_download_xlsx(self, tmp_path):
        result = _make_video("xlvid")
        files = download_video(result, tmp_path, formats=["xlsx"])
        xlsx_files = [f for f in files if f.suffix == ".xlsx"]
        assert len(xlsx_files) >= 1
        content = xlsx_files[0].read_text(encoding="utf-8")
        assert "<Workbook" in content

    def test_download_specific_formats(self, tmp_path):
        result = _make_video("fmtvid")
        files = download_video(result, tmp_path, formats=["json"])
        assert len(files) == 1
        assert files[0].suffix == ".json"


class TestDownloadBatch:
    def _make_batch(self) -> BatchResult:
        return BatchResult(
            total=2,
            succeeded=1,
            failed=1,
            results=[_make_video("vid1"), _make_video("vid2")],
            errors=[BatchError(url_or_id="bad1", error_type="TestError", error_message="Failed")],
        )

    def test_download_batch_creates_aggregate_files(self, tmp_path):
        batch = self._make_batch()
        files = download_batch(batch, tmp_path, formats=["json", "csv"])
        file_names = [f.name for f in files]
        assert "batch_result.json" in file_names
        assert "batch_summary.csv" in file_names
        assert "batch_all_comments.csv" in file_names

    def test_download_batch_creates_per_video_files(self, tmp_path):
        batch = self._make_batch()
        files = download_batch(batch, tmp_path, formats=["json"])
        file_names = [f.name for f in files]
        assert "vid1_result.json" in file_names
        assert "vid2_result.json" in file_names

    def test_download_batch_creates_directory(self, tmp_path):
        batch = self._make_batch()
        new_dir = tmp_path / "batch_output"
        files = download_batch(batch, new_dir, formats=["json"])
        assert new_dir.exists()
        assert len(files) > 0
