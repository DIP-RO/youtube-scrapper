"""Export scraped data to CSV, JSONL, and TXT formats.

These functions convert VideoResult and BatchResult objects into
formats commonly used by researchers and data analysts:

- **CSV**: For Excel, SPSS, R, pandas
- **JSONL**: For streaming/NLP pipelines (one JSON object per line)
- **TXT**: For transcripts (plain text, one line per segment)
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .models import BatchResult, VideoResult


# ---------------------------------------------------------------------------
# Single video export
# ---------------------------------------------------------------------------

def video_to_csv(result: VideoResult) -> str:
    """Convert a VideoResult to a CSV string with metadata + engagement.

    Returns a single-row CSV with headers.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "video_id", "title", "channel_name", "channel_id", "views",
        "likes", "comment_count", "upload_date", "duration_seconds",
        "category", "is_live", "transcript_available", "transcript_language",
        "summary_available", "access_blocked", "source_url",
    ])
    writer.writerow([
        result.video_id,
        result.metadata.title or "",
        result.metadata.channel_name or "",
        result.metadata.channel_id or "",
        result.metadata.views or "",
        result.engagement.likes or "",
        result.engagement.comment_count or "",
        result.metadata.upload_date or "",
        result.metadata.duration_seconds or "",
        result.metadata.category or "",
        result.metadata.is_live or "",
        result.transcript.available,
        result.transcript.language or "",
        result.summary.available,
        result.network.access_status.blocked,
        result.source_url,
    ])
    return output.getvalue()


def comments_to_csv(result: VideoResult) -> str:
    """Convert a VideoResult's comments to a CSV string.

    Each row is one comment with author, text, likes, published date, etc.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "video_id", "comment_id", "author", "author_channel_id",
        "text", "likes", "reply_count", "is_pinned", "is_hearted", "published",
    ])
    for c in result.comments:
        writer.writerow([
            result.video_id,
            c.comment_id or "",
            c.author or "",
            c.author_channel_id or "",
            c.text or "",
            c.likes,
            c.reply_count,
            c.is_pinned,
            c.is_hearted,
            c.published or "",
        ])
    return output.getvalue()


def transcript_to_txt(result: VideoResult) -> str:
    """Convert a VideoResult's transcript to plain text.

    Format: ``[MM:SS] text`` per segment, or just text if no timestamps.
    """
    if not result.transcript.available:
        return ""
    lines: list[str] = []
    for seg in result.transcript.segments:
        if seg.start_ms is not None:
            minutes = seg.start_ms // 60000
            seconds = (seg.start_ms % 60000) // 1000
            lines.append(f"[{minutes:02d}:{seconds:02d}] {seg.text}")
        else:
            lines.append(seg.text)
    return "\n".join(lines) if lines else (result.transcript.text or "")


def video_to_jsonl(result: VideoResult) -> str:
    """Convert a VideoResult to a single JSONL line."""
    return json.dumps(result.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Batch export
# ---------------------------------------------------------------------------

def batch_to_csv(batch: BatchResult) -> str:
    """Convert a BatchResult to CSV with one row per video."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "video_id", "title", "channel_name", "views", "likes",
        "comment_count", "upload_date", "duration_seconds",
        "transcript_available", "access_blocked", "status",
    ])
    for result in batch.results:
        writer.writerow([
            result.video_id,
            result.metadata.title or "",
            result.metadata.channel_name or "",
            result.metadata.views or "",
            result.engagement.likes or "",
            result.engagement.comment_count or "",
            result.metadata.upload_date or "",
            result.metadata.duration_seconds or "",
            result.transcript.available,
            result.network.access_status.blocked,
            "ok",
        ])
    for err in batch.errors:
        writer.writerow([
            "", "", "", "", "", "", "", "", "", "",
            f"error: {err.error_type}",
        ])
    return output.getvalue()


def batch_to_jsonl(batch: BatchResult) -> str:
    """Convert a BatchResult to JSONL (one JSON object per line).

    Each line is either a result or an error.
    """
    lines: list[str] = []
    for result in batch.results:
        d = result.to_dict()
        d["_status"] = "ok"
        lines.append(json.dumps(d, ensure_ascii=False))
    for err in batch.errors:
        lines.append(json.dumps({
            "_status": "error",
            "url_or_id": err.url_or_id,
            "error_type": err.error_type,
            "error_message": err.error_message,
        }, ensure_ascii=False))
    return "\n".join(lines)


def batch_comments_to_csv(batch: BatchResult) -> str:
    """Export all comments from all videos in a batch to a single CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "video_id", "comment_id", "author", "author_channel_id",
        "text", "likes", "reply_count", "is_pinned", "is_hearted", "published",
    ])
    for result in batch.results:
        for c in result.comments:
            writer.writerow([
                result.video_id,
                c.comment_id or "",
                c.author or "",
                c.author_channel_id or "",
                c.text or "",
                c.likes,
                c.reply_count,
                c.is_pinned,
                c.is_hearted,
                c.published or "",
            ])
    return output.getvalue()


# ---------------------------------------------------------------------------
# Generic export dispatcher
# ---------------------------------------------------------------------------

def export_video(result: VideoResult, format: str, comments: bool = False) -> str:
    """Export a single VideoResult to the specified format.

    Args:
        result: The VideoResult to export.
        format: One of "json", "csv", "jsonl", "txt".
        comments: If True and format is "csv", export comments instead of metadata.

    Returns:
        String content in the requested format.
    """
    format = format.lower().strip()
    if format == "json":
        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    if format == "csv":
        return comments_to_csv(result) if comments else video_to_csv(result)
    if format == "jsonl":
        return video_to_jsonl(result)
    if format == "txt":
        return transcript_to_txt(result)
    raise ValueError(f"Unknown format: {format!r}. Use json, csv, jsonl, or txt.")


def export_batch(batch: BatchResult, format: str, comments: bool = False) -> str:
    """Export a BatchResult to the specified format.

    Args:
        batch: The BatchResult to export.
        format: One of "json", "csv", "jsonl".
        comments: If True and format is "csv", export all comments from all videos.

    Returns:
        String content in the requested format.
    """
    format = format.lower().strip()
    if format == "json":
        return json.dumps(batch.to_dict(), ensure_ascii=False, indent=2)
    if format == "csv":
        return batch_comments_to_csv(batch) if comments else batch_to_csv(batch)
    if format == "jsonl":
        return batch_to_jsonl(batch)
    raise ValueError(f"Unknown format: {format!r}. Use json, csv, or jsonl.")
