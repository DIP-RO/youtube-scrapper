"""Research data preparation utilities for fast, structured dataset building.

This module provides high-level helpers that researchers can use to
quickly prepare datasets from YouTube videos without wasting time on
boilerplate. It covers the most common research workflows:

1. **Dataset collection** — scrape a list of videos and get a clean
   pandas-ready CSV/JSONL dataset with metadata, engagement, and
   sentiment in one call.

2. **Comment corpus** — collect all comments from multiple videos into
   a single CSV ready for NLP analysis (sentiment, topic modeling,
   qualitative coding).

3. **Transcript corpus** — collect all transcripts into a single file
   for text analysis (LDA, embeddings, discourse analysis).

4. **Channel research** — scrape all videos from a channel and prepare
   a structured dataset with channel-level statistics.

5. **Comparative analysis** — scrape multiple videos and produce a
   comparison table with engagement rates, sentiment scores, and
   metadata side-by-side.

6. **Pandas integration** — convert any scraped data directly into a
   pandas DataFrame without manual parsing.

All helpers use the existing scraper, export, sentiment, and filter
modules under the hood — they just wrap them in researcher-friendly
APIs that produce ready-to-analyze output.

Example::

    from media_data_extractor.research import collect_dataset

    # One call → CSV dataset ready for analysis
    df = collect_dataset(
        urls=["URL1", "URL2", "URL3"],
        output_path="dataset.csv",
        include_sentiment=True,
        include_comments=True,
    )
    print(df.head())
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .client import ScraperConfig, YouTubeScraper
from .export import (
    batch_comments_to_csv,
    batch_to_csv,
    batch_to_jsonl,
    comments_to_csv,
    transcript_to_txt,
    video_to_csv,
)
from .filters import CommentFilter, filter_comments
from .models import BatchResult, Comment, VideoResult
from .sentiment import analyze_video_sentiment, VideoSentiment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class DatasetSummary:
    """Summary of a prepared dataset.

    Attributes:
        total_videos: Total videos processed.
        succeeded: Videos successfully scraped.
        failed: Videos that failed.
        total_comments: Total comments collected.
        total_transcripts: Transcripts collected.
        sentiment_available: Videos with sentiment analysis.
        output_files: Files produced.
        elapsed_seconds: Total time.
    """

    total_videos: int = 0
    succeeded: int = 0
    failed: int = 0
    total_comments: int = 0
    total_transcripts: int = 0
    sentiment_available: int = 0
    output_files: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_videos": self.total_videos,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "total_comments": self.total_comments,
            "total_transcripts": self.total_transcripts,
            "sentiment_available": self.sentiment_available,
            "output_files": self.output_files,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }

    def __str__(self) -> str:
        return (
            f"Dataset: {self.succeeded}/{self.total_videos} videos, "
            f"{self.total_comments} comments, "
            f"{self.total_transcripts} transcripts, "
            f"{self.sentiment_available} sentiments, "
            f"{len(self.output_files)} files, "
            f"{self.elapsed_seconds:.1f}s"
        )


# ---------------------------------------------------------------------------
# 1. Dataset collection — one call → ready-to-analyze CSV/JSONL
# ---------------------------------------------------------------------------

def collect_dataset(
    urls: list[str],
    output_path: str | None = None,
    output_format: str = "csv",
    include_sentiment: bool = True,
    include_comments: bool = False,
    include_transcripts: bool = False,
    max_comments: int = 25,
    max_workers: int = 3,
    comment_filter: CommentFilter | None = None,
    checkpoint: str | None = None,
) -> tuple[list[dict[str, Any]], DatasetSummary]:
    """Collect a structured dataset from a list of YouTube videos.

    This is the primary research helper. One call scrapes all videos,
    optionally analyzes sentiment, and produces a clean dataset ready
    for pandas, R, SPSS, or Excel.

    Args:
        urls: List of YouTube URLs or video IDs.
        output_path: If provided, save the dataset to this file.
        output_format: "csv", "jsonl", or "json".
        include_sentiment: Add sentiment columns (positive/negative/neutral counts).
        include_comments: Also export all comments to a separate file.
        include_transcripts: Also export all transcripts to a separate file.
        max_comments: Max comments to scrape per video.
        max_workers: Concurrent browser instances.
        comment_filter: Optional filter to apply to comments before export.
        checkpoint: Optional checkpoint file for crash recovery.

    Returns:
        Tuple of (list of row dicts, DatasetSummary).

    Example::

        rows, summary = collect_dataset(
            urls=["URL1", "URL2"],
            output_path="research_dataset.csv",
            include_sentiment=True,
        )
        import pandas as pd
        df = pd.DataFrame(rows)
    """
    import time

    start = time.time()
    config = ScraperConfig(max_comments=max_comments, max_workers=max_workers)
    summary = DatasetSummary(total_videos=len(urls))
    rows: list[dict[str, Any]] = []
    sentiments: list[VideoSentiment] = []
    all_results: list[VideoResult] = []

    with YouTubeScraper(config) as scraper:
        batch = scraper.batch_scrape(urls, checkpoint=checkpoint)

    summary.succeeded = batch.succeeded
    summary.failed = batch.failed
    all_results = batch.results

    # Count comments and transcripts
    summary.total_comments = sum(len(r.comments) for r in all_results)
    summary.total_transcripts = sum(1 for r in all_results if r.transcript.available)

    # Apply comment filter if provided
    if comment_filter:
        for r in all_results:
            r.comments = filter_comments(r, filter=comment_filter)

    # Build rows with sentiment
    for result in all_results:
        row = _video_to_research_row(result)
        if include_sentiment:
            try:
                sentiment = analyze_video_sentiment(result)
                sentiments.append(sentiment)
                row.update(_sentiment_to_row(sentiment))
                summary.sentiment_available += 1
            except Exception as exc:
                logger.warning("Sentiment failed for %s: %s", result.video_id, exc)
                row.update(_sentiment_to_row_empty())
        rows.append(row)

    # Write output files
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if output_format == "csv":
            _write_csv(rows, out)
            summary.output_files.append(str(out))
        elif output_format == "jsonl":
            _write_jsonl(rows, out)
            summary.output_files.append(str(out))
        elif output_format == "json":
            out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summary.output_files.append(str(out))

        # Optional: comments file
        if include_comments:
            comments_path = out.with_name(out.stem + "_comments.csv")
            comments_path.write_text(batch_comments_to_csv(batch), encoding="utf-8")
            summary.output_files.append(str(comments_path))

        # Optional: transcripts file
        if include_transcripts:
            transcripts_path = out.with_name(out.stem + "_transcripts.txt")
            lines = []
            for r in all_results:
                if r.transcript.available:
                    lines.append(f"=== {r.video_id}: {r.metadata.title} ===")
                    lines.append(transcript_to_txt(r))
                    lines.append("")
            transcripts_path.write_text("\n".join(lines), encoding="utf-8")
            summary.output_files.append(str(transcripts_path))

    summary.elapsed_seconds = time.time() - start
    logger.info("Dataset collected: %s", summary)
    return rows, summary


# ---------------------------------------------------------------------------
# 2. Comment corpus — all comments in one CSV for NLP
# ---------------------------------------------------------------------------

def collect_comment_corpus(
    urls: list[str],
    output_path: str | None = None,
    max_comments: int = 100,
    max_workers: int = 3,
    comment_filter: CommentFilter | None = None,
    include_sentiment: bool = False,
) -> tuple[list[dict[str, Any]], DatasetSummary]:
    """Collect all comments from multiple videos into a single corpus.

    Produces a flat CSV/JSONL with one row per comment, tagged with
    the source video. Ready for NLP pipelines, sentiment analysis,
    topic modeling, or qualitative coding.

    Args:
        urls: List of YouTube URLs or video IDs.
        output_path: If provided, save the comment corpus to this file.
        max_comments: Max comments per video (use high values for research).
        max_workers: Concurrent browser instances.
        comment_filter: Optional filter (e.g., min_likes=5 for quality).
        include_sentiment: Add per-comment sentiment label and score.

    Returns:
        Tuple of (list of comment dicts, DatasetSummary).

    Example::

        comments, summary = collect_comment_corpus(
            urls=["URL1", "URL2"],
            output_path="comments.csv",
            max_comments=500,
            include_sentiment=True,
        )
    """
    import time

    from .sentiment import analyze_sentiment

    start = time.time()
    config = ScraperConfig(max_comments=max_comments, max_workers=max_workers)
    summary = DatasetSummary(total_videos=len(urls))
    comment_rows: list[dict[str, Any]] = []

    with YouTubeScraper(config) as scraper:
        batch = scraper.batch_scrape(urls)

    summary.succeeded = batch.succeeded
    summary.failed = batch.failed

    for result in batch.results:
        comments = result.comments
        if comment_filter:
            comments = filter_comments(result, filter=comment_filter)

        for c in comments:
            row = {
                "video_id": result.video_id,
                "video_title": result.metadata.title or "",
                "comment_id": c.comment_id or "",
                "author": c.author or "",
                "text": c.text or "",
                "likes": c.likes,
                "reply_count": c.reply_count,
                "is_pinned": c.is_pinned,
                "is_hearted": c.is_hearted,
                "published": c.published or "",
            }
            if include_sentiment:
                try:
                    s = analyze_sentiment(c.text or "")
                    row["sentiment_label"] = s.label
                    row["sentiment_compound"] = round(s.compound, 4)
                    row["sentiment_positive"] = s.positive
                    row["sentiment_negative"] = s.negative
                except Exception:
                    row["sentiment_label"] = "neutral"
                    row["sentiment_compound"] = 0.0
            comment_rows.append(row)

    summary.total_comments = len(comment_rows)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(comment_rows, out)
        summary.output_files.append(str(out))

    summary.elapsed_seconds = time.time() - start
    return comment_rows, summary


# ---------------------------------------------------------------------------
# 3. Transcript corpus — all transcripts in one file for text analysis
# ---------------------------------------------------------------------------

def collect_transcript_corpus(
    urls: list[str],
    output_path: str | None = None,
    output_format: str = "txt",
    include_metadata: bool = True,
    max_workers: int = 3,
) -> tuple[list[dict[str, Any]], DatasetSummary]:
    """Collect all transcripts from multiple videos into a single corpus.

    Produces a text file or JSONL with all transcripts, suitable for:
    - Topic modeling (LDA, BERTopic)
    - Embedding-based analysis
    - Discourse analysis
    - Readability analysis

    Args:
        urls: List of YouTube URLs or video IDs.
        output_path: If provided, save the corpus to this file.
        output_format: "txt" (one file, separated by headers) or "jsonl"
            (one JSON object per video with transcript + metadata).
        include_metadata: Include video title, channel, duration in output.
        max_workers: Concurrent browser instances.

    Returns:
        Tuple of (list of transcript dicts, DatasetSummary).

    Example::

        transcripts, summary = collect_transcript_corpus(
            urls=["URL1", "URL2"],
            output_path="transcripts.jsonl",
            output_format="jsonl",
        )
    """
    import time

    start = time.time()
    config = ScraperConfig(max_workers=max_workers)
    summary = DatasetSummary(total_videos=len(urls))
    transcript_rows: list[dict[str, Any]] = []

    with YouTubeScraper(config) as scraper:
        batch = scraper.batch_scrape(urls)

    summary.succeeded = batch.succeeded
    summary.failed = batch.failed

    for result in batch.results:
        if not result.transcript.available:
            continue
        row: dict[str, Any] = {
            "video_id": result.video_id,
            "transcript": result.transcript.text or "",
            "language": result.transcript.language or "",
            "segments": [
                {
                    "text": seg.text,
                    "start_ms": seg.start_ms,
                    "duration_ms": seg.duration_ms,
                }
                for seg in result.transcript.segments
            ],
        }
        if include_metadata:
            row["title"] = result.metadata.title or ""
            row["channel"] = result.metadata.channel_name or ""
            row["duration_seconds"] = result.metadata.duration_seconds
            row["upload_date"] = result.metadata.upload_date or ""
            row["category"] = result.metadata.category or ""
        transcript_rows.append(row)
        summary.total_transcripts += 1

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if output_format == "jsonl":
            _write_jsonl(transcript_rows, out)
        else:  # txt
            lines = []
            for r in transcript_rows:
                if include_metadata:
                    lines.append(f"=== {r['video_id']}: {r.get('title', '')} ===")
                    lines.append(f"Channel: {r.get('channel', '')}")
                    lines.append(f"Duration: {r.get('duration_seconds', '')}s")
                    lines.append(f"Date: {r.get('upload_date', '')}")
                    lines.append("")
                lines.append(r["transcript"])
                lines.append("\n" + "=" * 60 + "\n")
            out.write_text("\n".join(lines), encoding="utf-8")
        summary.output_files.append(str(out))

    summary.elapsed_seconds = time.time() - start
    return transcript_rows, summary


# ---------------------------------------------------------------------------
# 4. Comparative analysis — side-by-side engagement comparison
# ---------------------------------------------------------------------------

def collect_comparison_table(
    urls: list[str],
    output_path: str | None = None,
    include_sentiment: bool = True,
    max_comments: int = 25,
    max_workers: int = 3,
) -> tuple[list[dict[str, Any]], DatasetSummary]:
    """Build a comparative analysis table across multiple videos.

    Each row is a video with engagement rates, sentiment scores, and
    key metrics side-by-side. Ideal for comparing videos in a study.

    Columns include:
    - video_id, title, channel, views, likes, dislikes, comment_count
    - like_rate (likes/views), comment_rate (comments/views)
    - engagement_rate ((likes+comments)/views)
    - sentiment_positive_pct, sentiment_negative_pct, sentiment_neutral_pct
    - sentiment_avg_compound
    - transcript_available, duration_seconds, upload_date

    Args:
        urls: List of YouTube URLs or video IDs.
        output_path: If provided, save as CSV.
        include_sentiment: Include sentiment analysis columns.
        max_comments: Max comments per video.
        max_workers: Concurrent browser instances.

    Returns:
        Tuple of (list of comparison rows, DatasetSummary).
    """
    import time

    start = time.time()
    config = ScraperConfig(max_comments=max_comments, max_workers=max_workers)
    summary = DatasetSummary(total_videos=len(urls))
    rows: list[dict[str, Any]] = []

    with YouTubeScraper(config) as scraper:
        batch = scraper.batch_scrape(urls)

    summary.succeeded = batch.succeeded
    summary.failed = batch.failed

    for result in batch.results:
        views = result.metadata.views or 0
        likes = result.engagement.likes or 0
        comment_count = result.engagement.comment_count or 0
        dislikes = result.engagement.dislikes
        dislike_count = dislikes.dislikes if dislikes else 0

        row = {
            "video_id": result.video_id,
            "title": result.metadata.title or "",
            "channel": result.metadata.channel_name or "",
            "views": views,
            "likes": likes,
            "dislikes": dislike_count,
            "comment_count": comment_count,
            "duration_seconds": result.metadata.duration_seconds or 0,
            "upload_date": result.metadata.upload_date or "",
            "transcript_available": result.transcript.available,
            "like_rate": round(likes / views, 6) if views else 0,
            "comment_rate": round(comment_count / views, 6) if views else 0,
            "engagement_rate": round((likes + comment_count) / views, 6) if views else 0,
            "dislike_rate": round(dislike_count / views, 6) if views else 0,
        }

        if include_sentiment:
            try:
                sentiment = analyze_video_sentiment(result)
                total = sentiment.total_comments or 1
                row["sentiment_positive_pct"] = round(sentiment.positive_count / total, 4)
                row["sentiment_negative_pct"] = round(sentiment.negative_count / total, 4)
                row["sentiment_neutral_pct"] = round(sentiment.neutral_count / total, 4)
                row["sentiment_avg_compound"] = round(sentiment.average_compound, 4)
                row["sentiment_label"] = sentiment.overall_label
                summary.sentiment_available += 1
            except Exception:
                row["sentiment_positive_pct"] = 0
                row["sentiment_negative_pct"] = 0
                row["sentiment_neutral_pct"] = 0
                row["sentiment_avg_compound"] = 0
                row["sentiment_label"] = "unknown"

        rows.append(row)
        summary.total_comments += len(result.comments)

    # Sort by views descending
    rows.sort(key=lambda r: r.get("views", 0), reverse=True)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(rows, out)
        summary.output_files.append(str(out))

    summary.elapsed_seconds = time.time() - start
    return rows, summary


# ---------------------------------------------------------------------------
# 5. Pandas integration — convert scraped data to DataFrame
# ---------------------------------------------------------------------------

def to_dataframe(rows: list[dict[str, Any]]):
    """Convert scraped data rows to a pandas DataFrame.

    Args:
        rows: List of dicts from collect_dataset, collect_comment_corpus,
            collect_comparison_table, etc.

    Returns:
        pandas.DataFrame

    Example::

        rows, _ = collect_dataset(urls=["URL1", "URL2"])
        df = to_dataframe(rows)
        print(df.describe())
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "pandas is required for to_dataframe(). "
            "Install it with: pip install pandas"
        ) from exc
    return pd.DataFrame(rows)


def batch_to_dataframe(batch: BatchResult, include_sentiment: bool = False):
    """Convert a BatchResult directly to a pandas DataFrame.

    Args:
        batch: A BatchResult from batch_scrape.
        include_sentiment: Add sentiment columns.

    Returns:
        pandas.DataFrame with one row per video.
    """
    rows = []
    for result in batch.results:
        row = _video_to_research_row(result)
        if include_sentiment:
            try:
                sentiment = analyze_video_sentiment(result)
                row.update(_sentiment_to_row(sentiment))
            except Exception:
                row.update(_sentiment_to_row_empty())
        rows.append(row)
    return to_dataframe(rows)


def comments_to_dataframe(
    results: list[VideoResult],
    include_sentiment: bool = False,
):
    """Convert scraped comments to a pandas DataFrame.

    Args:
        results: List of VideoResult objects.
        include_sentiment: Add per-comment sentiment.

    Returns:
        pandas.DataFrame with one row per comment.
    """
    from .sentiment import analyze_sentiment

    rows = []
    for result in results:
        for c in result.comments:
            row = {
                "video_id": result.video_id,
                "comment_id": c.comment_id or "",
                "author": c.author or "",
                "text": c.text or "",
                "likes": c.likes,
                "reply_count": c.reply_count,
                "is_pinned": c.is_pinned,
                "is_hearted": c.is_hearted,
                "published": c.published or "",
            }
            if include_sentiment:
                try:
                    s = analyze_sentiment(c.text or "")
                    row["sentiment_label"] = s.label
                    row["sentiment_compound"] = s.compound
                except Exception:
                    row["sentiment_label"] = "neutral"
                    row["sentiment_compound"] = 0.0
            rows.append(row)
    return to_dataframe(rows)


# ---------------------------------------------------------------------------
# 6. Quick scrape — minimal one-video research output
# ---------------------------------------------------------------------------

def quick_scrape(
    url: str,
    output_dir: str | None = None,
    formats: tuple[str, ...] = ("json", "csv"),
    max_comments: int = 25,
) -> dict[str, Any]:
    """Scrape a single video and return a dict ready for analysis.

    The fastest way to get data from one video. Returns a flat dict
    with all metadata, engagement, and optionally saves files.

    Args:
        url: YouTube URL or video ID.
        output_dir: If provided, save JSON/CSV/TXT files here.
        formats: Output formats when saving ("json", "csv", "txt", "srt").
        max_comments: Max comments to scrape.

    Returns:
        Flat dict with all video data.

    Example::

        data = quick_scrape("dQw4w9WgXcQ")
        print(data["title"], data["views"], data["sentiment_label"])
    """
    config = ScraperConfig(max_comments=max_comments)
    with YouTubeScraper(config) as scraper:
        result = scraper.get_video(url)

    row = _video_to_research_row(result)
    try:
        sentiment = analyze_video_sentiment(result)
        row.update(_sentiment_to_row(sentiment))
    except Exception:
        pass

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for fmt in formats:
            if fmt == "json":
                (out / f"{result.video_id}.json").write_text(
                    json.dumps(row, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            elif fmt == "csv":
                _write_csv([row], out / f"{result.video_id}.csv")
            elif fmt == "txt":
                (out / f"{result.video_id}_transcript.txt").write_text(
                    transcript_to_txt(result), encoding="utf-8",
                )
            elif fmt == "srt":
                from .export import transcript_to_srt
                (out / f"{result.video_id}.srt").write_text(
                    transcript_to_srt(result), encoding="utf-8",
                )

    return row


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _video_to_research_row(result: VideoResult) -> dict[str, Any]:
    """Convert a VideoResult to a flat dict for tabular data."""
    return {
        "video_id": result.video_id,
        "title": result.metadata.title or "",
        "description": (result.metadata.description or "")[:500],  # Truncate for CSV
        "channel_name": result.metadata.channel_name or "",
        "channel_id": result.metadata.channel_id or "",
        "channel_subscribers": result.metadata.channel_subscribers or "",
        "views": result.metadata.views or 0,
        "likes": result.engagement.likes or 0,
        "comment_count": result.engagement.comment_count or 0,
        "comments_scraped": result.engagement.comment_count_scraped,
        "dislikes": result.engagement.dislikes.dislikes if result.engagement.dislikes else None,
        "upload_date": result.metadata.upload_date or "",
        "duration_seconds": result.metadata.duration_seconds or 0,
        "category": result.metadata.category or "",
        "is_live": result.metadata.is_live or False,
        "transcript_available": result.transcript.available,
        "transcript_language": result.transcript.language or "",
        "transcript_text": (result.transcript.text or "")[:1000],  # Truncate
        "summary_available": result.summary.available,
        "summary_text": (result.summary.text or "")[:500],
        "keywords": "|".join(result.metadata.keywords or []),
        "thumbnail": result.metadata.thumbnail or "",
        "source_url": result.source_url,
        "access_blocked": result.network.access_status.blocked,
    }


def _sentiment_to_row(sentiment: VideoSentiment) -> dict[str, Any]:
    """Convert a VideoSentiment to flat dict columns."""
    total = sentiment.total_comments or 1
    return {
        "sentiment_label": sentiment.overall_label,
        "sentiment_positive_count": sentiment.positive_count,
        "sentiment_negative_count": sentiment.negative_count,
        "sentiment_neutral_count": sentiment.neutral_count,
        "sentiment_positive_pct": round(sentiment.positive_count / total, 4),
        "sentiment_negative_pct": round(sentiment.negative_count / total, 4),
        "sentiment_neutral_pct": round(sentiment.neutral_count / total, 4),
        "sentiment_avg_compound": round(sentiment.average_compound, 4),
        "sentiment_total_comments": sentiment.total_comments,
    }


def _sentiment_to_row_empty() -> dict[str, Any]:
    """Empty sentiment columns for failed analysis."""
    return {
        "sentiment_label": "unknown",
        "sentiment_positive_count": 0,
        "sentiment_negative_count": 0,
        "sentiment_neutral_count": 0,
        "sentiment_positive_pct": 0,
        "sentiment_negative_pct": 0,
        "sentiment_neutral_pct": 0,
        "sentiment_avg_compound": 0,
        "sentiment_total_comments": 0,
    }


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """Write a list of dicts to a CSV file."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys(), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(output.getvalue(), encoding="utf-8")


def _write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    """Write a list of dicts to a JSONL file (one JSON per line)."""
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
