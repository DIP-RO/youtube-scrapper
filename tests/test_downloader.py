"""Tests for the video downloader module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from yt_network_scraper.downloader import (
    _extension_for_mime,
    _parse_format,
    download_stream,
    download_video,
    extract_streams,
    has_ffmpeg,
    merge_audio_video,
    select_best_audio,
    select_best_progressive,
    select_best_video,
    select_by_quality,
    select_worst_progressive,
)
from yt_network_scraper.models import DownloadResult, StreamFormat


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_format(
    itag: int = 22,
    url: str = "https://example.com/stream",
    mime_type: str = "video/mp4",
    has_audio: bool = True,
    has_video: bool = True,
    height: int | None = 720,
    width: int | None = 1280,
    bitrate: int = 1000000,
    content_length: int | None = 5000000,
    quality: str = "medium",
    quality_label: str = "720p",
    is_adaptive: bool = False,
) -> StreamFormat:
    note = "progressive" if not is_adaptive else ("DASH audio" if has_audio and not has_video else "DASH video")
    return StreamFormat(
        itag=itag,
        url=url,
        mime_type=mime_type,
        quality=quality,
        quality_label=quality_label,
        bitrate=bitrate,
        width=width,
        height=height,
        content_length=content_length,
        has_audio=has_audio,
        has_video=has_video,
        format_note=note,
    )


def _make_player_response(
    include_progressive: bool = True,
    include_adaptive: bool = True,
    include_encrypted: bool = False,
) -> dict:
    """Create a mock ytInitialPlayerResponse with streamingData."""
    streaming_data: dict = {}

    if include_progressive:
        streaming_data["formats"] = [
            {
                "itag": 18,
                "url": "https://example.com/360p.mp4",
                "mimeType": "video/mp4; codecs=\"avc1.42001E, mp4a.40.2\"",
                "quality": "small",
                "qualityLabel": "360p",
                "bitrate": 500000,
                "width": 640,
                "height": 360,
                "contentLength": "1000000",
            },
            {
                "itag": 22,
                "url": "https://example.com/720p.mp4",
                "mimeType": "video/mp4; codecs=\"avc1.64001F, mp4a.40.2\"",
                "quality": "hd720",
                "qualityLabel": "720p",
                "bitrate": 1000000,
                "width": 1280,
                "height": 720,
                "contentLength": "5000000",
            },
        ]

    if include_adaptive:
        streaming_data["adaptiveFormats"] = [
            # Video-only formats
            {
                "itag": 137,
                "url": "https://example.com/1080p_video.mp4",
                "mimeType": "video/mp4; codecs=\"avc1.640028\"",
                "quality": "hd1080",
                "qualityLabel": "1080p",
                "bitrate": 3000000,
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "contentLength": "50000000",
            },
            {
                "itag": 136,
                "url": "https://example.com/720p_video.mp4",
                "mimeType": "video/mp4; codecs=\"avc1.4d401f\"",
                "quality": "hd720",
                "qualityLabel": "720p",
                "bitrate": 2000000,
                "width": 1280,
                "height": 720,
                "fps": 30,
                "contentLength": "20000000",
            },
            # Audio-only formats
            {
                "itag": 140,
                "url": "https://example.com/audio_128.m4a",
                "mimeType": "audio/mp4; codecs=\"mp4a.40.2\"",
                "quality": "medium",
                "bitrate": 128000,
                "contentLength": "2000000",
            },
            {
                "itag": 139,
                "url": "https://example.com/audio_48.m4a",
                "mimeType": "audio/mp4; codecs=\"mp4a.40.2\"",
                "quality": "low",
                "bitrate": 48000,
                "contentLength": "500000",
            },
        ]

    if include_encrypted:
        streaming_data["formats"] = streaming_data.get("formats", []) + [
            {
                "itag": 999,
                "signatureCipher": "s=encrypted&url=https://example.com/encrypted.mp4",
                "mimeType": "video/mp4",
                "quality": "hd720",
                "qualityLabel": "720p",
            }
        ]

    return {"streamingData": streaming_data}


# ---------------------------------------------------------------------------
# extract_streams tests
# ---------------------------------------------------------------------------

class TestExtractStreams:
    def test_extracts_progressive_formats(self):
        player = _make_player_response(include_adaptive=False)
        formats = extract_streams(player)
        assert len(formats) == 2
        assert all(f.has_audio and f.has_video for f in formats)

    def test_extracts_adaptive_formats(self):
        player = _make_player_response(include_progressive=False)
        formats = extract_streams(player)
        assert len(formats) == 4
        video_formats = [f for f in formats if f.has_video and not f.has_audio]
        audio_formats = [f for f in formats if f.has_audio and not f.has_video]
        assert len(video_formats) == 2
        assert len(audio_formats) == 2

    def test_extracts_all_formats(self):
        player = _make_player_response()
        formats = extract_streams(player)
        assert len(formats) == 6

    def test_empty_streaming_data(self):
        formats = extract_streams({})
        assert formats == []

    def test_no_streaming_data_key(self):
        formats = extract_streams({"videoDetails": {}})
        assert formats == []

    def test_skips_encrypted_formats(self):
        player = _make_player_response(include_progressive=False, include_adaptive=False, include_encrypted=True)
        formats = extract_streams(player)
        # Encrypted format should be skipped
        assert len(formats) == 0

    def test_skips_formats_without_url(self):
        player = {
            "streamingData": {
                "formats": [
                    {"itag": 1, "mimeType": "video/mp4"},  # No URL
                ],
                "adaptiveFormats": [],
            }
        }
        formats = extract_streams(player)
        assert len(formats) == 0

    def test_parses_content_length(self):
        player = _make_player_response(include_adaptive=False)
        formats = extract_streams(player)
        assert formats[0].content_length == 1000000
        assert formats[1].content_length == 5000000

    def test_handles_missing_content_length(self):
        player = {
            "streamingData": {
                "formats": [
                    {"itag": 18, "url": "https://example.com/vid.mp4", "mimeType": "video/mp4"},
                ],
                "adaptiveFormats": [],
            }
        }
        formats = extract_streams(player)
        assert formats[0].content_length is None


# ---------------------------------------------------------------------------
# _parse_format tests
# ---------------------------------------------------------------------------

class TestParseFormat:
    def test_progressive_format(self):
        fmt = {
            "itag": 22,
            "url": "https://example.com/vid.mp4",
            "mimeType": "video/mp4",
            "qualityLabel": "720p",
        }
        result = _parse_format(fmt, is_adaptive=False)
        assert result is not None
        assert result.has_audio is True
        assert result.has_video is True
        assert result.format_note == "progressive"

    def test_adaptive_video(self):
        fmt = {
            "itag": 137,
            "url": "https://example.com/vid.mp4",
            "mimeType": "video/mp4; codecs=\"avc1\"",
        }
        result = _parse_format(fmt, is_adaptive=True)
        assert result is not None
        assert result.has_video is True
        assert result.has_audio is False
        assert result.format_note == "DASH video"

    def test_adaptive_audio(self):
        fmt = {
            "itag": 140,
            "url": "https://example.com/audio.m4a",
            "mimeType": "audio/mp4",
        }
        result = _parse_format(fmt, is_adaptive=True)
        assert result is not None
        assert result.has_audio is True
        assert result.has_video is False
        assert result.format_note == "DASH audio"

    def test_signature_cipher_skipped(self):
        fmt = {"itag": 999, "signatureCipher": "s=xxx", "mimeType": "video/mp4"}
        result = _parse_format(fmt, is_adaptive=False)
        assert result is None

    def test_cipher_skipped(self):
        fmt = {"itag": 999, "cipher": "s=xxx", "mimeType": "video/mp4"}
        result = _parse_format(fmt, is_adaptive=False)
        assert result is None

    def test_no_url_returns_none(self):
        fmt = {"itag": 1, "mimeType": "video/mp4"}
        result = _parse_format(fmt, is_adaptive=False)
        assert result is None


# ---------------------------------------------------------------------------
# Format selection tests
# ---------------------------------------------------------------------------

class TestSelectBestVideo:
    def test_selects_highest_resolution(self):
        formats = [
            _make_format(itag=136, height=720, bitrate=2000000, has_audio=False),
            _make_format(itag=137, height=1080, bitrate=3000000, has_audio=False),
            _make_format(itag=160, height=144, bitrate=100000, has_audio=False),
        ]
        best = select_best_video(formats)
        assert best is not None
        assert best.itag == 137
        assert best.height == 1080

    def test_no_video_formats(self):
        formats = [
            _make_format(itag=140, has_audio=True, has_video=False, height=None, width=None),
        ]
        best = select_best_video(formats)
        assert best is None


class TestSelectBestAudio:
    def test_selects_highest_bitrate(self):
        formats = [
            _make_format(itag=140, has_audio=True, has_video=False, height=None, width=None, bitrate=128000),
            _make_format(itag=139, has_audio=True, has_video=False, height=None, width=None, bitrate=48000),
        ]
        best = select_best_audio(formats)
        assert best is not None
        assert best.itag == 140
        assert best.bitrate == 128000

    def test_no_audio_formats(self):
        formats = [
            _make_format(itag=137, has_audio=False, has_video=True, height=1080),
        ]
        best = select_best_audio(formats)
        assert best is None


class TestSelectBestProgressive:
    def test_selects_highest_progressive(self):
        formats = [
            _make_format(itag=18, height=360, bitrate=500000),
            _make_format(itag=22, height=720, bitrate=1000000),
        ]
        best = select_best_progressive(formats)
        assert best is not None
        assert best.itag == 22
        assert best.height == 720

    def test_no_progressive_formats(self):
        formats = [
            _make_format(itag=137, has_audio=False, has_video=True, height=1080),
        ]
        best = select_best_progressive(formats)
        assert best is None


class TestSelectWorstProgressive:
    def test_selects_lowest_progressive(self):
        formats = [
            _make_format(itag=18, height=360, bitrate=500000),
            _make_format(itag=22, height=720, bitrate=1000000),
        ]
        worst = select_worst_progressive(formats)
        assert worst is not None
        assert worst.itag == 18
        assert worst.height == 360


class TestSelectByQuality:
    def test_best_quality(self):
        formats = [
            _make_format(itag=18, height=360, quality_label="360p"),
            _make_format(itag=22, height=720, quality_label="720p"),
        ]
        best = select_by_quality(formats, "best")
        assert best is not None
        assert best.height == 720

    def test_worst_quality(self):
        formats = [
            _make_format(itag=18, height=360, quality_label="360p"),
            _make_format(itag=22, height=720, quality_label="720p"),
        ]
        worst = select_by_quality(formats, "worst")
        assert worst is not None
        assert worst.height == 360

    def test_specific_quality_720p(self):
        formats = [
            _make_format(itag=18, height=360, quality_label="360p"),
            _make_format(itag=22, height=720, quality_label="720p"),
        ]
        result = select_by_quality(formats, "720p")
        assert result is not None
        assert result.height == 720

    def test_audio_quality(self):
        formats = [
            _make_format(itag=140, has_audio=True, has_video=False, height=None, width=None, bitrate=128000),
            _make_format(itag=22, height=720),
        ]
        result = select_by_quality(formats, "audio")
        assert result is not None
        assert result.has_audio is True
        assert result.has_video is False

    def test_quality_not_found(self):
        formats = [_make_format(itag=22, height=720, quality_label="720p")]
        result = select_by_quality(formats, "999p")
        assert result is None

    def test_falls_back_to_video_only(self):
        formats = [
            _make_format(itag=137, has_audio=False, has_video=True, height=1080, quality_label="1080p"),
            _make_format(itag=22, height=720, quality_label="720p"),
        ]
        result = select_by_quality(formats, "1080p")
        assert result is not None
        assert result.height == 1080
        assert result.has_video is True
        assert result.has_audio is False

    def test_height_match_fallback(self):
        formats = [
            _make_format(itag=137, has_audio=False, has_video=True, height=1080, quality_label=None),
        ]
        result = select_by_quality(formats, "1080p")
        assert result is not None
        assert result.height == 1080


# ---------------------------------------------------------------------------
# download_stream tests
# ---------------------------------------------------------------------------

class TestDownloadStream:
    def test_successful_download(self, tmp_path):
        stream = _make_format(url="https://example.com/vid.mp4", content_length=100)
        output = tmp_path / "video.mp4"

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content.return_value = [b"x" * 50, b"x" * 50]
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        size = download_stream(stream, output, session=mock_session)
        assert size == 100
        assert output.exists()
        assert output.stat().st_size == 100

    def test_progress_callback(self, tmp_path):
        stream = _make_format(url="https://example.com/vid.mp4")
        output = tmp_path / "video.mp4"

        progress_calls: list[tuple[int, int, float]] = []

        def callback(downloaded: int, total: int, speed: float) -> None:
            progress_calls.append((downloaded, total, speed))

        mock_response = MagicMock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content.return_value = [b"x" * 50, b"x" * 50]
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        download_stream(stream, output, session=mock_session, progress_callback=callback)
        assert len(progress_calls) == 2
        assert progress_calls[0][0] == 50
        assert progress_calls[1][0] == 100

    def test_creates_parent_directory(self, tmp_path):
        stream = _make_format(url="https://example.com/vid.mp4")
        output = tmp_path / "subdir" / "deeper" / "video.mp4"

        mock_response = MagicMock()
        mock_response.headers = {"content-length": "10"}
        mock_response.iter_content.return_value = [b"x" * 10]
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        download_stream(stream, output, session=mock_session)
        assert output.exists()

    def test_empty_response(self, tmp_path):
        stream = _make_format(url="https://example.com/vid.mp4")
        output = tmp_path / "video.mp4"

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = []
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        size = download_stream(stream, output, session=mock_session)
        assert size == 0


# ---------------------------------------------------------------------------
# download_video (high-level) tests
# ---------------------------------------------------------------------------

class TestDownloadVideo:
    def test_no_formats_returns_error(self, tmp_path):
        result = download_video([], "vid1", tmp_path / "out.mp4")
        assert not result.success
        assert "No downloadable" in result.error

    def test_audio_only_download(self, tmp_path):
        formats = [
            _make_format(itag=140, has_audio=True, has_video=False, height=None, width=None,
                         mime_type="audio/mp4", bitrate=128000, quality="medium", quality_label=None),
        ]
        output = tmp_path / "audio.m4a"

        mock_response = MagicMock()
        mock_response.headers = {"content-length": "2000"}
        mock_response.iter_content.return_value = [b"x" * 2000]
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        result = download_video(formats, "vid1", output, quality="audio", session=mock_session)
        assert result.success
        assert result.file_size_bytes == 2000
        assert "audio" in result.output_path or str(output) in result.output_path

    def test_progressive_download(self, tmp_path):
        formats = [
            _make_format(itag=18, height=360, quality_label="360p", mime_type="video/mp4",
                         content_length=1000),
            _make_format(itag=22, height=720, quality_label="720p", mime_type="video/mp4",
                         content_length=5000),
        ]
        output = tmp_path / "video.mp4"

        mock_response = MagicMock()
        mock_response.headers = {"content-length": "5000"}
        mock_response.iter_content.return_value = [b"x" * 5000]
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        result = download_video(formats, "vid1", output, quality="best", session=mock_session)
        assert result.success
        assert result.file_size_bytes == 5000
        assert result.merged is False

    def test_quality_not_found(self, tmp_path):
        formats = [_make_format(itag=22, height=720, quality_label="720p")]
        result = download_video(formats, "vid1", tmp_path / "out.mp4", quality="999p")
        assert not result.success
        assert "No stream found" in result.error

    def test_adaptive_video_without_audio(self, tmp_path):
        """Test adaptive video-only format with no audio stream available."""
        formats = [
            _make_format(itag=137, has_audio=False, has_video=True, height=1080,
                         quality_label="1080p", mime_type="video/mp4", content_length=50000),
        ]
        output = tmp_path / "video.mp4"

        mock_response = MagicMock()
        mock_response.headers = {"content-length": "50000"}
        mock_response.iter_content.return_value = [b"x" * 50000]
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        result = download_video(formats, "vid1", output, quality="1080p", session=mock_session)
        assert result.success
        assert result.file_size_bytes == 50000
        assert result.merged is False

    def test_download_failure_returns_error(self, tmp_path):
        formats = [_make_format(itag=22, height=720, quality_label="720p")]
        output = tmp_path / "video.mp4"

        mock_session = MagicMock()
        mock_session.get.side_effect = requests.RequestException("Connection failed")

        result = download_video(formats, "vid1", output, quality="720p", session=mock_session)
        assert not result.success
        assert "Download failed" in result.error


# ---------------------------------------------------------------------------
# _extension_for_mime tests
# ---------------------------------------------------------------------------

class TestExtensionForMime:
    def test_mp4_video(self):
        assert _extension_for_mime("video/mp4; codecs=\"avc1\"") == "mp4"

    def test_webm_video(self):
        assert _extension_for_mime("video/webm; codecs=\"vp9\"") == "webm"

    def test_mp4_audio(self):
        assert _extension_for_mime("audio/mp4; codecs=\"mp4a\"") == "m4a"

    def test_webm_audio(self):
        assert _extension_for_mime("audio/webm; codecs=\"opus\"") == "webm"

    def test_unknown(self):
        assert _extension_for_mime("application/octet-stream") == "mp4"


# ---------------------------------------------------------------------------
# has_ffmpeg and merge_audio_video tests
# ---------------------------------------------------------------------------

class TestFfmpeg:
    def test_has_ffmpeg_returns_bool(self):
        result = has_ffmpeg()
        assert isinstance(result, bool)

    @patch("yt_network_scraper.downloader.shutil.which", return_value=None)
    def test_no_ffmpeg(self, _mock):
        assert has_ffmpeg() is False

    @patch("yt_network_scraper.downloader.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_has_ffmpeg(self, _mock):
        assert has_ffmpeg() is True

    @patch("yt_network_scraper.downloader.has_ffmpeg", return_value=False)
    def test_merge_without_ffmpeg(self, _mock, tmp_path):
        result = merge_audio_video(
            tmp_path / "video.mp4",
            tmp_path / "audio.m4a",
            tmp_path / "out.mp4",
        )
        assert result is False

    @patch("yt_network_scraper.downloader.has_ffmpeg", return_value=True)
    @patch("yt_network_scraper.downloader.subprocess.run")
    def test_merge_success(self, mock_run, _mock_ffmpeg, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr=b"", stdout=b"")
        # Create dummy files
        (tmp_path / "video.mp4").write_bytes(b"video")
        (tmp_path / "audio.m4a").write_bytes(b"audio")
        result = merge_audio_video(
            tmp_path / "video.mp4",
            tmp_path / "audio.m4a",
            tmp_path / "out.mp4",
        )
        assert result is True
        mock_run.assert_called_once()

    @patch("yt_network_scraper.downloader.has_ffmpeg", return_value=True)
    @patch("yt_network_scraper.downloader.subprocess.run")
    def test_merge_ffmpeg_failure(self, mock_run, _mock_ffmpeg, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr=b"error", stdout=b"")
        (tmp_path / "video.mp4").write_bytes(b"video")
        (tmp_path / "audio.m4a").write_bytes(b"audio")
        result = merge_audio_video(
            tmp_path / "video.mp4",
            tmp_path / "audio.m4a",
            tmp_path / "out.mp4",
        )
        assert result is False


# ---------------------------------------------------------------------------
# DownloadResult model tests
# ---------------------------------------------------------------------------

class TestDownloadResult:
    def test_success_property_true(self):
        result = DownloadResult(
            video_id="vid1",
            output_path="/tmp/video.mp4",
            file_size_bytes=1000,
        )
        assert result.success is True

    def test_success_property_false_with_error(self):
        result = DownloadResult(
            video_id="vid1",
            error="Download failed",
        )
        assert result.success is False

    def test_success_property_false_with_zero_size(self):
        result = DownloadResult(
            video_id="vid1",
            file_size_bytes=0,
        )
        assert result.success is False

    def test_to_dict(self):
        result = DownloadResult(
            video_id="vid1",
            output_path="/tmp/video.mp4",
            file_size_bytes=1000,
            quality="720p",
        )
        d = result.to_dict()
        assert d["video_id"] == "vid1"
        assert d["file_size_bytes"] == 1000
        assert d["quality"] == "720p"


# ---------------------------------------------------------------------------
# StreamFormat model tests
# ---------------------------------------------------------------------------

class TestStreamFormat:
    def test_to_dict(self):
        fmt = StreamFormat(
            itag=22,
            url="https://example.com/vid.mp4",
            mime_type="video/mp4",
            quality="hd720",
            quality_label="720p",
            height=720,
            width=1280,
        )
        d = fmt.to_dict()
        assert d["itag"] == 22
        assert d["url"] == "https://example.com/vid.mp4"
        assert d["height"] == 720
