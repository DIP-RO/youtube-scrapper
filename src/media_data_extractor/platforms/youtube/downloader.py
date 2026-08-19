"""YouTube video file downloader.

Extracts stream URLs from YouTube's ``streamingData`` payload and
downloads video/audio files. Supports:

- **Progressive formats** (combined audio+video, max 720p) — single file download
- **Adaptive formats** (separate video/audio, up to 4K) — downloads both and
  merges with ffmpeg if available, or saves separately
- **Audio-only extraction** — downloads just the audio stream
- **Quality selection** — "best", "worst", "720p", "1080p", "audio"

This module downloads public, non-DRM-protected videos only. It does not
bypass DRM, age gates, or authentication. Some videos (rentals,
members-only) cannot be downloaded.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

from ...core.models import DownloadResult, StreamFormat

logger = logging.getLogger(__name__)

# Progress callback type: (downloaded_bytes, total_bytes, speed_bps)
ProgressCallback = Any  # Callable[[int, int, float], None]

# Common YouTube itags for reference
# Progressive (audio+video combined):
#   18  = 360p mp4
#   22  = 720p mp4
#   36  = 240p 3gp
# Adaptive video-only:
#   137 = 1080p mp4
#   136 = 720p mp4
#   135 = 480p mp4
#   134 = 360p mp4
#   133 = 240p mp4
#   160 = 144p mp4
#   248 = 1080p webm
#   247 = 720p webm
#   271 = 1440p webm
#   313 = 2160p webm
# Adaptive audio-only:
#   140 = 128kbps m4a
#   139 = 48kbps m4a
#   251 = 160kbps webm
#   250 = 70kbps webm
#   249 = 50kbps webm


# ---------------------------------------------------------------------------
# Stream extraction from player response
# ---------------------------------------------------------------------------

def extract_streams(player: dict[str, Any]) -> list[StreamFormat]:
    """Extract all downloadable stream formats from a player response.

    Parses ``streamingData.formats`` (progressive) and
    ``streamingData.adaptiveFormats`` (DASH) from the player response.

    Args:
        player: The ``ytInitialPlayerResponse`` dict.

    Returns:
        List of :class:`StreamFormat` objects with download URLs.
    """
    streaming_data = player.get("streamingData", {})
    if not streaming_data:
        return []

    formats: list[StreamFormat] = []

    # Progressive formats (combined audio + video)
    for fmt in streaming_data.get("formats", []) or []:
        stream = _parse_format(fmt, is_adaptive=False)
        if stream:
            formats.append(stream)

    # Adaptive formats (separate audio or video)
    for fmt in streaming_data.get("adaptiveFormats", []) or []:
        stream = _parse_format(fmt, is_adaptive=True)
        if stream:
            formats.append(stream)

    return formats


def _parse_format(fmt: dict[str, Any], is_adaptive: bool) -> StreamFormat | None:
    """Parse a single format dict from streamingData into a StreamFormat."""
    url = fmt.get("url")
    if not url:
        # Some formats use signatureCipher (encrypted) — we don't decrypt
        # signatureCipher because that would require reverse-engineering
        # YouTube's player JavaScript, which is fragile and potentially
        # violates ToS. Skip these formats.
        cipher = fmt.get("signatureCipher") or fmt.get("cipher")
        if cipher:
            return None  # Encrypted URL — skip
        return None

    mime_type = fmt.get("mimeType", "")
    is_video = "video" in mime_type
    is_audio = "audio" in mime_type

    # For progressive formats, both audio and video are present
    if not is_adaptive:
        has_audio = True
        has_video = True
        note = "progressive"
    else:
        has_audio = is_audio
        has_video = is_video
        note = "DASH audio" if is_audio else "DASH video"

    content_length = fmt.get("contentLength")
    if content_length and content_length.isdigit():
        content_length_int = int(content_length)
    else:
        content_length_int = None

    return StreamFormat(
        itag=fmt.get("itag", 0),
        url=url,
        mime_type=mime_type,
        quality=fmt.get("quality", ""),
        quality_label=fmt.get("qualityLabel"),
        bitrate=fmt.get("bitrate"),
        width=fmt.get("width"),
        height=fmt.get("height"),
        fps=fmt.get("fps"),
        content_length=content_length_int,
        has_audio=has_audio,
        has_video=has_video,
        format_note=note,
    )


# ---------------------------------------------------------------------------
# Format selection
# ---------------------------------------------------------------------------

def select_best_video(formats: list[StreamFormat]) -> StreamFormat | None:
    """Select the highest quality video-only stream."""
    video_only = [f for f in formats if f.has_video and not f.has_audio]
    if not video_only:
        return None
    # Sort by height (resolution), then bitrate
    return max(video_only, key=lambda f: (f.height or 0, f.bitrate or 0))


def select_best_audio(formats: list[StreamFormat]) -> StreamFormat | None:
    """Select the highest quality audio-only stream."""
    audio_only = [f for f in formats if f.has_audio and not f.has_video]
    if not audio_only:
        return None
    return max(audio_only, key=lambda f: f.bitrate or 0)


def select_best_progressive(formats: list[StreamFormat]) -> StreamFormat | None:
    """Select the best progressive (combined audio+video) stream."""
    progressive = [f for f in formats if f.has_audio and f.has_video]
    if not progressive:
        return None
    return max(progressive, key=lambda f: (f.height or 0, f.bitrate or 0))


def select_worst_progressive(formats: list[StreamFormat]) -> StreamFormat | None:
    """Select the lowest quality progressive stream."""
    progressive = [f for f in formats if f.has_audio and f.has_video]
    if not progressive:
        return None
    return min(progressive, key=lambda f: (f.height or 0, f.bitrate or 0))


def select_by_quality(
    formats: list[StreamFormat],
    quality: str,
) -> StreamFormat | None:
    """Select a format by quality label (e.g. "720p", "1080p").

    Prefers progressive (combined) formats. Falls back to video-only
    if no progressive match is found.
    """
    quality_lower = quality.lower().strip()

    if quality_lower == "audio":
        return select_best_audio(formats)

    if quality_lower == "best":
        # Try progressive first, then adaptive+merge
        best_prog = select_best_progressive(formats)
        if best_prog:
            return best_prog
        return select_best_video(formats)

    if quality_lower == "worst":
        return select_worst_progressive(formats)

    # Match specific quality label (e.g. "720p")
    # Try progressive first
    for f in formats:
        if f.has_audio and f.has_video and f.quality_label == quality_lower:
            return f
    # Fall back to video-only
    for f in formats:
        if f.has_video and not f.has_audio and f.quality_label == quality_lower:
            return f
    # Try height match
    try:
        target_height = int(quality_lower.replace("p", ""))
    except ValueError:
        return None
    for f in formats:
        if f.has_audio and f.has_video and f.height == target_height:
            return f
    for f in formats:
        if f.has_video and not f.has_audio and f.height == target_height:
            return f
    return None


# ---------------------------------------------------------------------------
# File download
# ---------------------------------------------------------------------------

def download_stream(
    stream: StreamFormat,
    output_path: str | os.PathLike,
    session: requests.Session | None = None,
    progress_callback: ProgressCallback = None,
    chunk_size: int = 65536,
) -> int:
    """Download a single stream to a file.

    Args:
        stream: The StreamFormat to download.
        output_path: Path to save the file.
        session: Optional requests.Session to use.
        progress_callback: Optional callback(downloaded, total, speed_bps).
        chunk_size: Download chunk size in bytes.

    Returns:
        Number of bytes downloaded.

    Raises:
        requests.RequestException: If the download fails.
    """
    sess = session or requests.Session()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    response = sess.get(stream.url, stream=True, timeout=60)
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    downloaded = 0
    start_time = time.time()

    with open(out, "wb") as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    elapsed = time.time() - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    progress_callback(downloaded, total, speed)

    return downloaded


# ---------------------------------------------------------------------------
# ffmpeg detection and merging
# ---------------------------------------------------------------------------

def has_ffmpeg() -> bool:
    """Check if ffmpeg is available on the system."""
    return shutil.which("ffmpeg") is not None


def merge_audio_video(
    video_path: str | os.PathLike,
    audio_path: str | os.PathLike,
    output_path: str | os.PathLike,
) -> bool:
    """Merge audio and video files using ffmpeg.

    Args:
        video_path: Path to the video-only file.
        audio_path: Path to the audio-only file.
        output_path: Path for the merged output file.

    Returns:
        True if merge succeeded, False otherwise.
    """
    if not has_ffmpeg():
        logger.warning("ffmpeg not found — cannot merge audio and video")
        return False

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",  # Copy video stream without re-encoding
        "-c:a", "copy",  # Copy audio stream without re-encoding
        "-movflags", "+faststart",  # Web-optimized mp4
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,  # 5 minute timeout
        )
        if result.returncode != 0:
            logger.error("ffmpeg merge failed: %s", result.stderr.decode("utf-8", errors="replace"))
            return False
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.error("ffmpeg merge error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# High-level download function
# ---------------------------------------------------------------------------

def download_video(
    formats: list[StreamFormat],
    video_id: str,
    output_path: str | os.PathLike,
    quality: str = "best",
    session: requests.Session | None = None,
    progress_callback: ProgressCallback = None,
) -> DownloadResult:
    """Download a YouTube video file from extracted stream formats.

    This is the main download function. It selects the best format for
    the requested quality, downloads it, and optionally merges audio+video
    with ffmpeg.

    Args:
        formats: List of available StreamFormat objects.
        video_id: YouTube video ID (for logging/naming).
        output_path: Output file path (for progressive) or directory
            (for adaptive — will create video+audio files then merge).
        quality: Quality preference: "best", "worst", "720p", "1080p",
            "4k", "audio". Default: "best".
        session: Optional requests.Session with headers/cookies.
        progress_callback: Optional callback(downloaded, total, speed_bps).

    Returns:
        A :class:`DownloadResult` with download status and file info.
    """
    start_time = time.time()
    sess = session or requests.Session()

    if not formats:
        return DownloadResult(
            video_id=video_id,
            error="No downloadable stream formats found. Video may be DRM-protected, rental, or members-only.",
            elapsed_seconds=time.time() - start_time,
        )

    out = Path(output_path)
    quality_lower = quality.lower().strip()

    # Audio-only download
    if quality_lower == "audio":
        audio = select_best_audio(formats)
        if not audio:
            return DownloadResult(
                video_id=video_id,
                error="No audio-only stream available.",
                elapsed_seconds=time.time() - start_time,
            )
        # Determine extension from mime type
        ext = _extension_for_mime(audio.mime_type)
        if out.is_dir() or out.suffix == "":
            out = out / f"{video_id}_audio.{ext}"
        try:
            size = download_stream(audio, out, sess, progress_callback)
            return DownloadResult(
                video_id=video_id,
                output_path=str(out),
                format_itag=audio.itag,
                file_size_bytes=size,
                mime_type=audio.mime_type,
                quality="audio",
                elapsed_seconds=time.time() - start_time,
            )
        except Exception as exc:
            return DownloadResult(
                video_id=video_id,
                error=f"Download failed: {exc}",
                elapsed_seconds=time.time() - start_time,
            )

    # Select format based on quality preference
    selected = select_by_quality(formats, quality_lower)
    if not selected:
        available = sorted(set(f.quality_label or f.quality for f in formats if f.quality_label))
        return DownloadResult(
            video_id=video_id,
            error=f"No stream found for quality '{quality}'. Available: {', '.join(available) or 'none'}",
            elapsed_seconds=time.time() - start_time,
        )

    # Case 1: Progressive format (combined audio+video) — direct download
    if selected.has_audio and selected.has_video:
        ext = _extension_for_mime(selected.mime_type)
        if out.is_dir() or out.suffix == "":
            out = out / f"{video_id}.{ext}"
        try:
            size = download_stream(selected, out, sess, progress_callback)
            return DownloadResult(
                video_id=video_id,
                output_path=str(out),
                format_itag=selected.itag,
                file_size_bytes=size,
                mime_type=selected.mime_type,
                quality=selected.quality_label or selected.quality,
                elapsed_seconds=time.time() - start_time,
            )
        except Exception as exc:
            return DownloadResult(
                video_id=video_id,
                error=f"Download failed: {exc}",
                elapsed_seconds=time.time() - start_time,
            )

    # Case 2: Adaptive format (video-only) — need to also download audio and merge
    if selected.has_video and not selected.has_audio:
        audio = select_best_audio(formats)
        if not audio:
            # No audio stream — just download video-only
            ext = _extension_for_mime(selected.mime_type)
            if out.is_dir() or out.suffix == "":
                out = out / f"{video_id}_video.{ext}"
            try:
                size = download_stream(selected, out, sess, progress_callback)
                return DownloadResult(
                    video_id=video_id,
                    output_path=str(out),
                    format_itag=selected.itag,
                    file_size_bytes=size,
                    mime_type=selected.mime_type,
                    quality=selected.quality_label or selected.quality,
                    elapsed_seconds=time.time() - start_time,
                )
            except Exception as exc:
                return DownloadResult(
                    video_id=video_id,
                    error=f"Download failed: {exc}",
                    elapsed_seconds=time.time() - start_time,
                )

        # Download both video and audio, then merge
        ext = _extension_for_mime(selected.mime_type)
        if out.is_dir() or out.suffix == "":
            out = out / f"{video_id}.{ext}"
        elif out.suffix:
            ext = out.suffix.lstrip(".")

        out.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="ytns_") as tmpdir:
            tmp = Path(tmpdir)
            video_file = tmp / f"{video_id}_video.{ext}"
            audio_ext = _extension_for_mime(audio.mime_type)
            audio_file = tmp / f"{video_id}_audio.{audio_ext}"

            try:
                # Download video
                video_size = download_stream(selected, video_file, sess, progress_callback)
                # Download audio
                audio_size = download_stream(audio, audio_file, sess, progress_callback)
            except Exception as exc:
                return DownloadResult(
                    video_id=video_id,
                    error=f"Stream download failed: {exc}",
                    elapsed_seconds=time.time() - start_time,
                )

            # Try to merge with ffmpeg
            if has_ffmpeg():
                merged = merge_audio_video(video_file, audio_file, out)
                if merged:
                    final_size = out.stat().st_size
                    return DownloadResult(
                        video_id=video_id,
                        output_path=str(out),
                        format_itag=selected.itag,
                        file_size_bytes=final_size,
                        mime_type=selected.mime_type,
                        quality=selected.quality_label or selected.quality,
                        merged=True,
                        audio_path=str(audio_file),
                        video_path=str(video_file),
                        elapsed_seconds=time.time() - start_time,
                    )
                else:
                    logger.warning("ffmpeg merge failed — saving video and audio separately")
            else:
                logger.warning("ffmpeg not available — saving video and audio separately")

            # No ffmpeg or merge failed — save video and audio separately
            # Copy from temp to output directory
            final_video = out.parent / f"{video_id}_video.{ext}"
            final_audio = out.parent / f"{video_id}_audio.{audio_ext}"
            shutil.copy2(video_file, final_video)
            shutil.copy2(audio_file, final_audio)

            return DownloadResult(
                video_id=video_id,
                output_path=str(final_video),
                format_itag=selected.itag,
                file_size_bytes=final_video.stat().st_size,
                mime_type=selected.mime_type,
                quality=selected.quality_label or selected.quality,
                merged=False,
                audio_path=str(final_audio),
                video_path=str(final_video),
                elapsed_seconds=time.time() - start_time,
            )

    return DownloadResult(
        video_id=video_id,
        error="No suitable format found for the requested quality.",
        elapsed_seconds=time.time() - start_time,
    )


def _extension_for_mime(mime_type: str) -> str:
    """Get file extension for a MIME type."""
    # Check audio first — "audio/mp4" should return "m4a", not "mp4"
    if "audio" in mime_type:
        if "webm" in mime_type:
            return "webm"
        return "m4a"  # mp4 audio, m4a, aac
    if "mp4" in mime_type:
        return "mp4"
    if "webm" in mime_type:
        return "webm"
    if "3gp" in mime_type:
        return "3gp"
    if "flv" in mime_type:
        return "flv"
    return "mp4"
