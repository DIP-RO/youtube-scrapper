"""Export scraped data to CSV, JSONL, TXT, and Excel (XML SpreadsheetML) formats.

These functions convert VideoResult and BatchResult objects into
formats commonly used by researchers and data analysts:

- **CSV**: For Excel, SPSS, R, pandas
- **JSONL**: For streaming/NLP pipelines (one JSON object per line)
- **TXT**: For transcripts (plain text, one line per segment)
- **XLSX**: Excel XML SpreadsheetML 2003 format (no dependency needed)
- **SRT**: SubRip subtitle format for transcripts
"""

from __future__ import annotations

import csv
import html
import io
import json
import os
from pathlib import Path
from typing import Any

from ..core.models import BatchResult, VideoResult


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
    if format in ("xlsx", "xls"):
        return video_to_xlsx(result, comments=comments)
    if format == "srt":
        return transcript_to_srt(result)
    raise ValueError(f"Unknown format: {format!r}. Use json, csv, jsonl, txt, xlsx, or srt.")


def export_batch(batch: BatchResult, format: str, comments: bool = False) -> str:
    """Export a BatchResult to the specified format.

    Args:
        batch: The BatchResult to export.
        format: One of "json", "csv", "jsonl", "xlsx".
        comments: If True and format is "csv" or "xlsx", export all comments.

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
    if format in ("xlsx", "xls"):
        return batch_to_xlsx(batch, comments=comments)
    raise ValueError(f"Unknown format: {format!r}. Use json, csv, jsonl, or xlsx.")


# ---------------------------------------------------------------------------
# Excel XML (SpreadsheetML 2003 — no dependency needed, Excel opens natively)
# ---------------------------------------------------------------------------

def _xml_escape(value: Any) -> str:
    """Escape a value for XML attributes/text."""
    return html.escape(str(value), quote=True)


def _rows_to_xlsx(rows: list[list[Any]], headers: list[str]) -> str:
    """Convert rows + headers to Excel XML SpreadsheetML 2003 format."""
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">',
        ' <Worksheet ss:Name="Sheet1">',
        '  <Table>',
    ]
    # Header row
    lines.append('   <Row>')
    for h in headers:
        lines.append(f'    <Cell><Data ss:Type="String">{_xml_escape(h)}</Data></Cell>')
    lines.append('   </Row>')
    # Data rows
    for row in rows:
        lines.append('   <Row>')
        for val in row:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                lines.append(f'    <Cell><Data ss:Type="Number">{_xml_escape(val)}</Data></Cell>')
            elif isinstance(val, bool):
                lines.append(f'    <Cell><Data ss:Type="String">{_xml_escape(val)}</Data></Cell>')
            else:
                lines.append(f'    <Cell><Data ss:Type="String">{_xml_escape(val)}</Data></Cell>')
        lines.append('   </Row>')
    lines.extend(['  </Table>', ' </Worksheet>', '</Workbook>'])
    return "\n".join(lines)


def video_to_xlsx(result: VideoResult, comments: bool = False) -> str:
    """Convert a VideoResult to Excel XML format."""
    if comments:
        headers = [
            "video_id", "comment_id", "author", "author_channel_id",
            "text", "likes", "reply_count", "is_pinned", "is_hearted", "published",
        ]
        rows = []
        for c in result.comments:
            rows.append([
                result.video_id, c.comment_id or "", c.author or "",
                c.author_channel_id or "", c.text or "", c.likes,
                c.reply_count, c.is_pinned, c.is_hearted, c.published or "",
            ])
        return _rows_to_xlsx(rows, headers)
    else:
        headers = [
            "video_id", "title", "channel_name", "views", "likes",
            "comment_count", "upload_date", "duration_seconds",
            "transcript_available", "access_blocked", "source_url",
        ]
        rows = [[
            result.video_id, result.metadata.title or "",
            result.metadata.channel_name or "", result.metadata.views or "",
            result.engagement.likes or "", result.engagement.comment_count or "",
            result.metadata.upload_date or "", result.metadata.duration_seconds or "",
            result.transcript.available, result.network.access_status.blocked,
            result.source_url,
        ]]
        return _rows_to_xlsx(rows, headers)


def batch_to_xlsx(batch: BatchResult, comments: bool = False) -> str:
    """Convert a BatchResult to Excel XML format."""
    if comments:
        headers = [
            "video_id", "comment_id", "author", "author_channel_id",
            "text", "likes", "reply_count", "is_pinned", "is_hearted", "published",
        ]
        rows = []
        for result in batch.results:
            for c in result.comments:
                rows.append([
                    result.video_id, c.comment_id or "", c.author or "",
                    c.author_channel_id or "", c.text or "", c.likes,
                    c.reply_count, c.is_pinned, c.is_hearted, c.published or "",
                ])
        return _rows_to_xlsx(rows, headers)
    else:
        headers = [
            "video_id", "title", "channel_name", "views", "likes",
            "comment_count", "upload_date", "duration_seconds",
            "transcript_available", "access_blocked", "status",
        ]
        rows = []
        for result in batch.results:
            rows.append([
                result.video_id, result.metadata.title or "",
                result.metadata.channel_name or "", result.metadata.views or "",
                result.engagement.likes or "", result.engagement.comment_count or "",
                result.metadata.upload_date or "", result.metadata.duration_seconds or "",
                result.transcript.available, result.network.access_status.blocked, "ok",
            ])
        for err in batch.errors:
            rows.append(["", "", "", "", "", "", "", "", "", "", f"error: {err.error_type}"])
        return _rows_to_xlsx(rows, headers)


# ---------------------------------------------------------------------------
# SRT subtitle format
# ---------------------------------------------------------------------------

def transcript_to_srt(result: VideoResult) -> str:
    """Convert a VideoResult's transcript to SRT subtitle format.

    Format: index, timestamp range, text — standard SRT.
    """
    if not result.transcript.available:
        return ""
    lines: list[str] = []
    for i, seg in enumerate(result.transcript.segments, 1):
        start_ms = seg.start_ms or 0
        duration_ms = seg.duration_ms or 2000
        end_ms = start_ms + duration_ms
        lines.append(str(i))
        lines.append(f"{_ms_to_srt_time(start_ms)} --> {_ms_to_srt_time(end_ms)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)


def _ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT timestamp format: HH:MM:SS,mmm."""
    hours = ms // 3_600_000
    minutes = (ms % 3_600_000) // 60_000
    seconds = (ms % 60_000) // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


# ---------------------------------------------------------------------------
# Download / save to file
# ---------------------------------------------------------------------------

def download_video(
    result: VideoResult,
    output_dir: str | os.PathLike,
    formats: list[str] | None = None,
    include_comments: bool = True,
    include_transcript: bool = True,
) -> list[Path]:
    """Download (save) a scraped video result to files in the specified directory.

    Creates files in *output_dir* with the video ID as prefix:
    - ``{video_id}_metadata.csv`` — metadata CSV
    - ``{video_id}_comments.csv`` — comments CSV
    - ``{video_id}_transcript.txt`` — transcript plain text
    - ``{video_id}_transcript.srt`` — transcript SRT subtitles
    - ``{video_id}_result.json`` — full JSON result

    Args:
        result: The VideoResult to save.
        output_dir: Directory to save files into. Created if it doesn't exist.
        formats: List of formats to save (default: all). Options:
            "json", "csv", "txt", "srt", "xlsx".
        include_comments: Save comments CSV.
        include_transcript: Save transcript TXT and SRT.

    Returns:
        List of Path objects for all files created.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = result.video_id
    saved: list[Path] = []
    fmts = formats or ["json", "csv", "txt", "srt"]

    if "json" in fmts:
        p = out_dir / f"{vid}_result.json"
        p.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        saved.append(p)

    if "csv" in fmts:
        p = out_dir / f"{vid}_metadata.csv"
        p.write_text(video_to_csv(result), encoding="utf-8")
        saved.append(p)
        if include_comments:
            p = out_dir / f"{vid}_comments.csv"
            p.write_text(comments_to_csv(result), encoding="utf-8")
            saved.append(p)

    if "xlsx" in fmts:
        p = out_dir / f"{vid}_metadata.xlsx"
        p.write_text(video_to_xlsx(result), encoding="utf-8")
        saved.append(p)
        if include_comments:
            p = out_dir / f"{vid}_comments.xlsx"
            p.write_text(video_to_xlsx(result, comments=True), encoding="utf-8")
            saved.append(p)

    if include_transcript and result.transcript.available:
        if "txt" in fmts:
            p = out_dir / f"{vid}_transcript.txt"
            p.write_text(transcript_to_txt(result) + "\n", encoding="utf-8")
            saved.append(p)
        if "srt" in fmts:
            p = out_dir / f"{vid}_transcript.srt"
            p.write_text(transcript_to_srt(result) + "\n", encoding="utf-8")
            saved.append(p)

    return saved


def download_batch(
    batch: BatchResult,
    output_dir: str | os.PathLike,
    formats: list[str] | None = None,
    include_comments: bool = True,
) -> list[Path]:
    """Download (save) a batch result to files in the specified directory.

    Creates aggregate files plus per-video files:
    - ``batch_summary.csv`` — one row per video
    - ``batch_all_comments.csv`` — all comments from all videos
    - ``batch_result.json`` — full JSON batch result
    - Per-video files (same as :func:`download_video`)

    Args:
        batch: The BatchResult to save.
        output_dir: Directory to save files into.
        formats: List of formats to save (default: all).
        include_comments: Save comments CSV.

    Returns:
        List of Path objects for all files created.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    fmts = formats or ["json", "csv", "txt", "srt"]

    # Aggregate files
    if "json" in fmts:
        p = out_dir / "batch_result.json"
        p.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        saved.append(p)

    if "csv" in fmts:
        p = out_dir / "batch_summary.csv"
        p.write_text(batch_to_csv(batch), encoding="utf-8")
        saved.append(p)
        if include_comments:
            p = out_dir / "batch_all_comments.csv"
            p.write_text(batch_comments_to_csv(batch), encoding="utf-8")
            saved.append(p)

    if "xlsx" in fmts:
        p = out_dir / "batch_summary.xlsx"
        p.write_text(batch_to_xlsx(batch), encoding="utf-8")
        saved.append(p)

    # Per-video files
    for result in batch.results:
        saved.extend(download_video(result, out_dir, formats, include_comments))

    return saved
