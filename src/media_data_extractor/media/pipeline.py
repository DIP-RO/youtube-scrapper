"""Pipeline orchestration for end-to-end YouTube research workflows.

The pipeline chains multiple stages together:

    scrape → filter → sentiment → export → download

Each stage is optional and configurable. The pipeline handles errors
gracefully, continues on partial failures, and produces a comprehensive
result report.

Example::

    pipeline = ScrapePipeline(
        ScraperConfig(max_workers=4),
        stages=["scrape", "sentiment", "export", "download_video"],
        export_format="csv",
        download_dir="./downloads",
        output_dir="./output",
    )
    result = pipeline.run(["URL1", "URL2", "URL3"])
    print(f"Processed {result.succeeded} videos")
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..platforms.youtube.scraper import ScraperConfig, YouTubeScraper
from ..exporters._all import download_batch, download_video, export_batch, export_video
from ..analytics.filters import CommentFilter, filter_comments
from ..core.models import BatchResult, DownloadResult, VideoResult
from ..analytics.sentiment import analyze_video_sentiment, VideoSentiment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline result model
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PipelineStageResult:
    """Result of a single pipeline stage.

    Attributes:
        name: Stage name.
        succeeded: Number of items that succeeded.
        failed: Number of items that failed.
        elapsed_seconds: Time taken by this stage.
        error: Error message if the stage failed entirely.
    """

    name: str = ""
    succeeded: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "error": self.error,
        }


@dataclass(slots=True)
class PipelineResult:
    """Result of running the full pipeline.

    Attributes:
        total: Total videos processed.
        succeeded: Videos that completed all stages.
        failed: Videos that failed at some stage.
        stage_results: Per-stage results.
        elapsed_seconds: Total pipeline time.
        output_files: List of files produced.
        sentiments: Sentiment analysis results per video.
        video_downloads: Video download results per video.
    """

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    stage_results: list[PipelineStageResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    output_files: list[str] = field(default_factory=list)
    sentiments: list[VideoSentiment] = field(default_factory=list)
    video_downloads: list[DownloadResult] = field(default_factory=list)
    results: list[VideoResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "stage_results": [s.to_dict() for s in self.stage_results],
            "output_files": self.output_files,
            "sentiments": [s.to_dict() for s in self.sentiments],
            "video_downloads": [d.to_dict() for d in self.video_downloads],
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

VALID_STAGES = frozenset({
    "scrape",        # Scrape video metadata, comments, transcript
    "filter",        # Filter comments
    "sentiment",     # Analyze comment sentiment
    "export",        # Export to CSV/JSONL/TXT/XLSX
    "download",      # Download data files (metadata, comments, transcript)
    "download_video", # Download actual video files
})


class ScrapePipeline:
    """End-to-end pipeline for YouTube research workflows.

    Chains multiple processing stages together. Each stage receives the
    output of the previous stage and passes its output to the next.

    Args:
        config: ScraperConfig for the YouTubeScraper.
        stages: List of stage names to execute in order.
            Valid stages: scrape, filter, sentiment, export, download,
            download_video.
        export_format: Output format for export stage (json/csv/jsonl/txt/xlsx).
        download_dir: Directory for download stage.
        output_dir: Directory for export stage.
        comment_filter: CommentFilter for the filter stage.
        video_quality: Quality for video download stage.
        checkpoint: Optional checkpoint path for crash recovery.
        auto_resume: Enable auto-resume with retries.
        max_retries: Max retries for auto-resume.
    """

    def __init__(
        self,
        config: ScraperConfig | None = None,
        stages: list[str] | None = None,
        export_format: str = "json",
        download_dir: str | None = None,
        output_dir: str | None = None,
        comment_filter: CommentFilter | None = None,
        video_quality: str = "best",
        checkpoint: str | None = None,
        auto_resume: bool = False,
        max_retries: int = 3,
    ) -> None:
        self.config = config or ScraperConfig()
        self.stages = stages or ["scrape", "sentiment", "export"]
        # Validate stages
        invalid = [s for s in self.stages if s not in VALID_STAGES]
        if invalid:
            raise ValueError(f"Invalid pipeline stages: {invalid}. Valid: {VALID_STAGES}")
        self.export_format = export_format
        self.download_dir = download_dir
        self.output_dir = output_dir
        self.comment_filter = comment_filter
        self.video_quality = video_quality
        self.checkpoint = checkpoint
        self.auto_resume = auto_resume
        self.max_retries = max_retries

    def run(self, urls_or_ids: list[str]) -> PipelineResult:
        """Run the full pipeline on a list of URLs/IDs.

        Args:
            urls_or_ids: List of YouTube URLs or video IDs.

        Returns:
            A :class:`PipelineResult` with comprehensive results.
        """
        pipeline_start = time.time()
        result = PipelineResult(total=len(urls_or_ids))

        # Stage 1: Scrape
        batch: BatchResult | None = None
        if "scrape" in self.stages:
            stage_result, batch = self._run_scrape_stage(urls_or_ids)
            result.stage_results.append(stage_result)
            if stage_result.error:
                result.failed = len(urls_or_ids)
                result.elapsed_seconds = time.time() - pipeline_start
                return result
            result.results = batch.results if batch else []

        # Stage 2: Filter
        if "filter" in self.stages and result.results:
            stage_result = self._run_filter_stage(result.results)
            result.stage_results.append(stage_result)

        # Stage 3: Sentiment
        if "sentiment" in self.stages and result.results:
            stage_result = self._run_sentiment_stage(result.results, result)
            result.stage_results.append(stage_result)

        # Stage 4: Export
        if "export" in self.stages and batch:
            stage_result = self._run_export_stage(batch, result)
            result.stage_results.append(stage_result)

        # Stage 5: Download data files
        if "download" in self.stages and batch:
            stage_result = self._run_download_stage(batch, result)
            result.stage_results.append(stage_result)

        # Stage 6: Download video files
        if "download_video" in self.stages and result.results:
            stage_result = self._run_download_video_stage(result.results, result)
            result.stage_results.append(stage_result)

        # Summary
        result.succeeded = len(result.results)
        result.failed = result.total - result.succeeded
        result.elapsed_seconds = time.time() - pipeline_start

        logger.info(
            "Pipeline complete: %d succeeded, %d failed, %.1fs",
            result.succeeded, result.failed, result.elapsed_seconds,
        )
        return result

    def _run_scrape_stage(self, urls_or_ids: list[str]) -> tuple[PipelineStageResult, BatchResult | None]:
        """Run the scraping stage."""
        start = time.time()
        try:
            with YouTubeScraper(self.config) as scraper:
                if self.auto_resume and self.checkpoint:
                    batch = scraper.batch_scrape_resilient(
                        urls_or_ids,
                        progress_callback=None,
                        checkpoint=self.checkpoint,
                        max_retries=self.max_retries,
                    )
                else:
                    batch = scraper.batch_scrape(
                        urls_or_ids,
                        checkpoint=self.checkpoint,
                    )
            return PipelineStageResult(
                name="scrape",
                succeeded=batch.succeeded,
                failed=batch.failed,
                elapsed_seconds=time.time() - start,
            ), batch
        except Exception as exc:
            logger.error("Scrape stage failed: %s", exc)
            return PipelineStageResult(
                name="scrape",
                failed=len(urls_or_ids),
                elapsed_seconds=time.time() - start,
                error=str(exc),
            ), None

    def _run_filter_stage(self, results: list[VideoResult]) -> PipelineStageResult:
        """Run the comment filtering stage."""
        start = time.time()
        try:
            if self.comment_filter:
                for result in results:
                    filtered = filter_comments(result, filter=self.comment_filter)
                    result.comments = filtered
            succeeded = len(results)
            return PipelineStageResult(
                name="filter",
                succeeded=succeeded,
                elapsed_seconds=time.time() - start,
            )
        except Exception as exc:
            return PipelineStageResult(
                name="filter",
                failed=len(results),
                elapsed_seconds=time.time() - start,
                error=str(exc),
            )

    def _run_sentiment_stage(
        self,
        results: list[VideoResult],
        pipeline_result: PipelineResult,
    ) -> PipelineStageResult:
        """Run the sentiment analysis stage."""
        start = time.time()
        succeeded = 0
        failed = 0
        for result in results:
            try:
                sentiment = analyze_video_sentiment(result)
                pipeline_result.sentiments.append(sentiment)
                succeeded += 1
            except Exception as exc:
                logger.warning("Sentiment failed for %s: %s", result.video_id, exc)
                failed += 1
        return PipelineStageResult(
            name="sentiment",
            succeeded=succeeded,
            failed=failed,
            elapsed_seconds=time.time() - start,
        )

    def _run_export_stage(
        self,
        batch: BatchResult,
        pipeline_result: PipelineResult,
    ) -> PipelineStageResult:
        """Run the export stage."""
        start = time.time()
        try:
            if self.output_dir:
                out_dir = Path(self.output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                if self.export_format == "json":
                    p = out_dir / "batch_result.json"
                    content = export_batch(batch, format="json")
                elif self.export_format == "csv":
                    p = out_dir / "batch_summary.csv"
                    content = export_batch(batch, format="csv")
                elif self.export_format == "jsonl":
                    p = out_dir / "batch_result.jsonl"
                    content = export_batch(batch, format="jsonl")
                elif self.export_format == "xlsx":
                    p = out_dir / "batch_summary.xlsx"
                    content = export_batch(batch, format="xlsx")
                else:
                    p = out_dir / "batch_result.json"
                    content = export_batch(batch, format="json")
                p.write_text(content + "\n", encoding="utf-8")
                pipeline_result.output_files.append(str(p))
            return PipelineStageResult(
                name="export",
                succeeded=batch.succeeded,
                elapsed_seconds=time.time() - start,
            )
        except Exception as exc:
            return PipelineStageResult(
                name="export",
                failed=batch.succeeded,
                elapsed_seconds=time.time() - start,
                error=str(exc),
            )

    def _run_download_stage(
        self,
        batch: BatchResult,
        pipeline_result: PipelineResult,
    ) -> PipelineStageResult:
        """Run the data download stage."""
        start = time.time()
        try:
            if self.download_dir:
                files = download_batch(batch, self.download_dir)
                pipeline_result.output_files.extend(str(f) for f in files)
            return PipelineStageResult(
                name="download",
                succeeded=batch.succeeded,
                elapsed_seconds=time.time() - start,
            )
        except Exception as exc:
            return PipelineStageResult(
                name="download",
                failed=batch.succeeded,
                elapsed_seconds=time.time() - start,
                error=str(exc),
            )

    def _run_download_video_stage(
        self,
        results: list[VideoResult],
        pipeline_result: PipelineResult,
    ) -> PipelineStageResult:
        """Run the video file download stage."""
        start = time.time()
        succeeded = 0
        failed = 0
        if not self.download_dir:
            return PipelineStageResult(
                name="download_video",
                failed=len(results),
                elapsed_seconds=time.time() - start,
                error="No download_dir specified",
            )
        download_path = Path(self.download_dir) / "videos"
        download_path.mkdir(parents=True, exist_ok=True)
        try:
            with YouTubeScraper(self.config) as scraper:
                for result in results:
                    try:
                        dl_result = scraper.download_video_file(
                            result.video_id,
                            output_path=str(download_path / f"{result.video_id}.mp4"),
                            quality=self.video_quality,
                        )
                        pipeline_result.video_downloads.append(dl_result)
                        if dl_result.success:
                            pipeline_result.output_files.append(dl_result.output_path)
                            succeeded += 1
                        else:
                            failed += 1
                    except Exception as exc:
                        logger.warning("Video download failed for %s: %s", result.video_id, exc)
                        failed += 1
        except Exception as exc:
            return PipelineStageResult(
                name="download_video",
                failed=len(results),
                elapsed_seconds=time.time() - start,
                error=str(exc),
            )
        return PipelineStageResult(
            name="download_video",
            succeeded=succeeded,
            failed=failed,
            elapsed_seconds=time.time() - start,
        )
