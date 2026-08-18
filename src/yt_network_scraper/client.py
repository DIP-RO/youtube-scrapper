"""Main scraper client — orchestrates browser setup, page loading, and data collection.

Usage::

    from yt_network_scraper import YouTubeScraper, ScraperConfig

    config = ScraperConfig(max_comments=50, transcript_language="en")
    with YouTubeScraper(config) as scraper:
        result = scraper.get_video("dQw4w9WgXcQ")
        print(result.metadata.title)
        print(result.transcript.text)
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .exceptions import (
    AccessBlockedException,
    BrowserNotInitializedError,
    InvalidVideoURLError,
    ScraperError,
    SeleniumNotInstalledError,
)
from .models import (
    AccessStatus,
    BatchError,
    BatchResult,
    Comment,
    DislikeData,
    DownloadResult,
    Engagement,
    NetworkInfo,
    StreamFormat,
    Summary,
    Transcript,
    VideoMetadata,
    VideoResult,
)
from .parsing import (
    extract_api_key,
    extract_innertube_context,
    extract_json_assignment,
    extract_ytcfg,
    parse_metadata,
)
from .scraper import fetch_comment_data, fetch_dislikes, fetch_transcript
from .downloader import download_video as _download_video_file, extract_streams
from .utils import detect_access_block, extract_video_id, find_all_keys, find_key, int_or_none, summarize_text

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class ScraperConfig:
    """Configuration for :class:`YouTubeScraper`.

    Attributes:
        headless: Run Chrome in headless mode.
        timeout: Browser page-load timeout in seconds.
        max_comments: Maximum number of comments to fetch.
        transcript_language: Preferred ISO language code for transcripts.
        request_delay: Base delay (seconds) between fallback network requests.
        max_page_retries: Number of page-load retries when YouTube returns a block page.
        user_agent: User-Agent string for the browser and HTTP session.
        max_workers: Maximum number of concurrent browser instances for batch scraping.
        batch_delay: Delay (seconds) between starting each concurrent scrape task.
    """

    headless: bool = True
    timeout: int = 25
    max_comments: int = 25
    transcript_language: str = "en"
    request_delay: float = 1.5
    max_page_retries: int = 2
    user_agent: str = DEFAULT_USER_AGENT
    max_workers: int = 3
    batch_delay: float = 2.0


class YouTubeScraper:
    """Scrape YouTube video data from browser-captured and follow-up network payloads.

    The scraper opens a YouTube watch page in headless Chrome via Selenium,
    captures network responses through Chrome DevTools performance logs,
    extracts YouTube's initial JSON payloads, then uses the innertube API
    for transcripts and comments.  It does **not** scrape the DOM and does
    **not** attempt to bypass CAPTCHAs, bot detection, or authentication.

    Must be used as a context manager so the browser driver is properly
    initialized and cleaned up::

        with YouTubeScraper() as scraper:
            result = scraper.get_video("VIDEO_ID")
    """

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.config.user_agent,
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.youtube.com",
                "Referer": "https://www.youtube.com/",
            }
        )
        self.driver: Any | None = None

    # -- Context manager --------------------------------------------------

    def __enter__(self) -> "YouTubeScraper":
        self.driver = self._build_driver()
        return self

    def __exit__(self, *_exc: object) -> None:
        if self.driver is not None:
            self.driver.quit()
            self.driver = None

    # -- Public API -------------------------------------------------------

    def get_video(self, url_or_id: str) -> VideoResult:
        """Scrape a single YouTube video by URL or ID.

        Args:
            url_or_id: A YouTube watch URL, youtu.be URL, shorts URL, or
                bare 11-character video ID.

        Returns:
            A :class:`VideoResult` with metadata, transcript, comments,
            engagement metrics, and summary.

        Raises:
            InvalidVideoURLError: If the URL/ID cannot be parsed.
            AccessBlockedException: If YouTube returns an access challenge.
            SeleniumNotInstalledError: If Selenium is not available.
            BrowserNotInitializedError: If not used as a context manager.
        """
        try:
            video_id = extract_video_id(url_or_id)
        except ValueError as exc:
            raise InvalidVideoURLError(str(exc)) from exc

        watch_url = f"https://www.youtube.com/watch?v={video_id}&hl=en&persist_hl=1"
        html, network_events = self._load_watch_html(watch_url)
        access_dict = detect_access_block(html)
        access_status = AccessStatus(
            blocked=access_dict["blocked"],
            reasons=access_dict["reasons"],
            message=access_dict["message"],
        )

        player = extract_json_assignment(html, "ytInitialPlayerResponse") or {}
        initial = extract_json_assignment(html, "ytInitialData") or {}
        ytcfg = extract_ytcfg(html) or {}
        api_key = ytcfg.get("INNERTUBE_API_KEY") or extract_api_key(html, network_events)
        context = ytcfg.get("INNERTUBE_CONTEXT") or extract_innertube_context(html)

        metadata_dict = parse_metadata(video_id, player, initial)
        likes_from_metadata = metadata_dict.pop("_likes", None)

        transcript = fetch_transcript(
            self.session,
            player,
            self.config.transcript_language,
            initial=initial,
            api_key=api_key,
            context=context,
        )
        if not transcript.available:
            panel_transcript = self._trigger_transcript_panel_from_network()
            if panel_transcript.available:
                if not panel_transcript.language:
                    panel_transcript.language = transcript.language
                if not panel_transcript.name:
                    panel_transcript.name = transcript.name
                if panel_transcript.is_auto_generated is None:
                    panel_transcript.is_auto_generated = transcript.is_auto_generated
                transcript = panel_transcript

        comment_count, comments = fetch_comment_data(
            self.session,
            initial,
            api_key=api_key,
            context=context,
            max_comments=self.config.max_comments,
        )
        dislikes = fetch_dislikes(self.session, video_id)
        likes = likes_from_metadata
        if likes is None and dislikes and dislikes.likes is not None:
            likes = dislikes.likes

        summary_dict = summarize_text(
            transcript.text or metadata_dict.get("description") or ""
        )

        metadata = VideoMetadata(
            video_url=metadata_dict["video_url"],
            title=metadata_dict.get("title"),
            description=metadata_dict.get("description"),
            views=metadata_dict.get("views"),
            channel_name=metadata_dict.get("channel_name"),
            channel_id=metadata_dict.get("channel_id"),
            channel_url=metadata_dict.get("channel_url"),
            channel_subscribers=metadata_dict.get("channel_subscribers"),
            upload_date=metadata_dict.get("upload_date"),
            publish_date=metadata_dict.get("publish_date"),
            timestamp=metadata_dict.get("timestamp"),
            duration_seconds=metadata_dict.get("duration_seconds"),
            category=metadata_dict.get("category"),
            is_live=metadata_dict.get("is_live"),
            keywords=metadata_dict.get("keywords", []),
            thumbnail=metadata_dict.get("thumbnail"),
        )

        engagement = Engagement(
            likes=likes,
            views=metadata_dict.get("views"),
            dislikes=dislikes,
            comment_count=comment_count,
            comment_count_scraped=len(comments),
        )

        summary = Summary(
            available=summary_dict["available"],
            text=summary_dict["text"],
            method=summary_dict["method"],
        )

        network_info = NetworkInfo(
            access_status=access_status,
            api_key_found=bool(api_key),
            captured_event_count=len(network_events),
            dom_scraping=False,
            bot_evasion=False,
        )

        return VideoResult(
            video_id=video_id,
            source_url=watch_url,
            metadata=metadata,
            engagement=engagement,
            transcript=transcript,
            summary=summary,
            comments=comments,
            network=network_info,
        )

    def get_streams(self, url_or_id: str) -> list[StreamFormat]:
        """Extract downloadable stream formats for a video.

        Loads the watch page and extracts all available stream formats
        from the player response's ``streamingData``.

        Args:
            url_or_id: YouTube URL or video ID.

        Returns:
            List of :class:`StreamFormat` objects with download URLs.

        Raises:
            InvalidVideoURLError: If the URL/ID cannot be parsed.
            AccessBlockedException: If YouTube blocks access.
            BrowserNotInitializedError: If not used as a context manager.
        """
        if self.driver is None:
            raise BrowserNotInitializedError("YouTubeScraper must be used as a context manager")

        try:
            video_id = extract_video_id(url_or_id)
        except ValueError as exc:
            raise InvalidVideoURLError(str(exc)) from exc

        watch_url = f"https://www.youtube.com/watch?v={video_id}&hl=en&persist_hl=1"
        html, _ = self._load_watch_html(watch_url)
        player = extract_json_assignment(html, "ytInitialPlayerResponse") or {}
        return extract_streams(player)

    def download_video_file(
        self,
        url_or_id: str,
        output_path: str,
        quality: str = "best",
        progress_callback: Any = None,
    ) -> DownloadResult:
        """Download a YouTube video file to disk.

        Extracts stream URLs from the watch page, selects the best format
        for the requested quality, and downloads the file. For adaptive
        formats (high quality), audio and video are downloaded separately
        and merged with ffmpeg if available.

        Args:
            url_or_id: YouTube URL or video ID.
            output_path: File path (for progressive) or directory
                (for adaptive — file names auto-generated).
            quality: Quality preference: "best", "worst", "720p",
                "1080p", "4k", "audio". Default: "best".
            progress_callback: Optional callback(downloaded, total, speed).

        Returns:
            A :class:`DownloadResult` with download status and file path.

        Raises:
            InvalidVideoURLError: If the URL/ID cannot be parsed.
            BrowserNotInitializedError: If not used as a context manager.

        Example::

            with YouTubeScraper() as scraper:
                result = scraper.download_video_file(
                    "https://www.youtube.com/watch?v=VIDEO_ID",
                    output_path="./video.mp4",
                    quality="720p",
                )
                if result.success:
                    print(f"Downloaded to {result.output_path}")
        """
        if self.driver is None:
            raise BrowserNotInitializedError("YouTubeScraper must be used as a context manager")

        try:
            video_id = extract_video_id(url_or_id)
        except ValueError as exc:
            raise InvalidVideoURLError(str(exc)) from exc

        watch_url = f"https://www.youtube.com/watch?v={video_id}&hl=en&persist_hl=1"
        html, _ = self._load_watch_html(watch_url)
        player = extract_json_assignment(html, "ytInitialPlayerResponse") or {}
        formats = extract_streams(player)

        return _download_video_file(
            formats=formats,
            video_id=video_id,
            output_path=output_path,
            quality=quality,
            session=self.session,
            progress_callback=progress_callback,
        )

    def batch_scrape(
        self,
        urls_or_ids: list[str],
        max_workers: int | None = None,
        batch_delay: float | None = None,
        progress_callback: Any = None,
        checkpoint: str | None = None,
        retry_failed: bool = False,
    ) -> BatchResult:
        """Scrape multiple YouTube videos concurrently.

        Each video is scraped in its own browser instance, running in parallel
        using a thread pool. Failed videos are captured in the errors list
        without stopping the batch.

        Args:
            urls_or_ids: List of YouTube URLs, youtu.be URLs, or 11-char video IDs.
            max_workers: Override max concurrent workers (default: config.max_workers).
            batch_delay: Override delay between starting each task (default: config.batch_delay).
            progress_callback: Optional callable ``(index, total, video_id, status)`` called
                after each video completes. ``status`` is ``"ok"`` or ``"error"``.
            checkpoint: Optional path to a JSON file for crash-resumable batching.
                Completed results are saved incrementally. If the file already
                exists, already-completed videos are skipped on re-run.
            retry_failed: If True, videos that previously failed (status "error"
                in checkpoint) are retried. Only "ok" videos are skipped.
                Default False — all checkpointed videos are skipped.

        Returns:
            A :class:`BatchResult` with successful results and errors.

        Example::

            with YouTubeScraper(ScraperConfig(max_workers=4)) as scraper:
                batch = scraper.batch_scrape([
                    "https://youtu.be/VIDEO1",
                    "https://youtu.be/VIDEO2",
                    "VIDEO_ID_3",
                ])
                print(f"Succeeded: {batch.succeeded}, Failed: {batch.failed}")
                for result in batch.results:
                    print(result.video_id, result.metadata.title)
                for err in batch.errors:
                    print(err.url_or_id, err.error_message)
        """
        workers = max_workers or self.config.max_workers
        delay = batch_delay if batch_delay is not None else self.config.batch_delay

        # --- Checkpoint: load existing progress ---
        checkpoint_data: dict[str, dict] = {}
        if checkpoint:
            cp_path = Path(checkpoint)
            if cp_path.exists():
                try:
                    checkpoint_data = json.loads(cp_path.read_text(encoding="utf-8"))
                    logging.info("Loaded checkpoint: %d completed videos", len(checkpoint_data))
                except (json.JSONDecodeError, OSError):
                    checkpoint_data = {}

        # Separate already-completed from pending
        if retry_failed:
            # Only skip videos that succeeded; retry failed ones
            completed_urls = {
                url for url, entry in checkpoint_data.items()
                if entry.get("status") == "ok"
            }
        else:
            completed_urls = set(checkpoint_data.keys())
        pending_urls = [u for u in urls_or_ids if u not in completed_urls]
        skipped = len(urls_or_ids) - len(pending_urls)

        total = len(urls_or_ids)
        results: list[VideoResult] = []
        errors: list[BatchError] = []
        start_time = time.time()

        # Load checkpointed results into the results list
        for url_or_id in urls_or_ids:
            if url_or_id in checkpoint_data:
                cp_entry = checkpoint_data[url_or_id]
                if cp_entry.get("status") == "ok" and "result" in cp_entry:
                    results.append(self._deserialize_result(cp_entry["result"]))

        def _save_checkpoint() -> None:
            """Atomically save current progress to checkpoint file."""
            if not checkpoint:
                return
            data = dict(checkpoint_data)
            cp_path = Path(checkpoint)
            cp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = cp_path.with_suffix(cp_path.suffix + ".tmp")
            tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(cp_path)

        def _scrape_one(url_or_id: str) -> tuple[str, VideoResult | None, BatchError | None]:
            """Scrape a single video in its own browser instance."""
            try:
                scraper = YouTubeScraper(self.config)
                scraper.__enter__()
                try:
                    result = scraper.get_video(url_or_id)
                    return url_or_id, result, None
                finally:
                    scraper.__exit__()
            except ScraperError as exc:
                return url_or_id, None, BatchError(
                    url_or_id=url_or_id,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            except Exception as exc:  # noqa: BLE001
                return url_or_id, None, BatchError(
                    url_or_id=url_or_id,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )

        if pending_urls:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {}
                for i, url_or_id in enumerate(pending_urls):
                    if i > 0 and delay > 0:
                        time.sleep(delay)
                    future = executor.submit(_scrape_one, url_or_id)
                    futures[future] = url_or_id

                completed = 0
                for future in as_completed(futures):
                    url_or_id, result, error = future.result()
                    completed += 1
                    if result is not None:
                        results.append(result)
                        if checkpoint:
                            checkpoint_data[url_or_id] = {
                                "status": "ok",
                                "result": result.to_dict(),
                            }
                    else:
                        errors.append(error)  # type: ignore[arg-type]
                        if checkpoint:
                            checkpoint_data[url_or_id] = {
                                "status": "error",
                                "error_type": error.error_type,  # type: ignore[union-attr]
                                "error_message": error.error_message,  # type: ignore[union-attr]
                            }
                    if checkpoint:
                        _save_checkpoint()
                    if progress_callback is not None:
                        status = "ok" if result is not None else "error"
                        progress_callback(completed + skipped, total, url_or_id, status)

        elapsed = time.time() - start_time
        return BatchResult(
            total=total,
            succeeded=len(results),
            failed=len(errors),
            results=results,
            errors=errors,
            elapsed_seconds=round(elapsed, 2),
        )

    def batch_scrape_resilient(
        self,
        urls_or_ids: list[str],
        max_workers: int | None = None,
        batch_delay: float | None = None,
        progress_callback: Any = None,
        checkpoint: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> BatchResult:
        """Scrape multiple videos with automatic crash recovery.

        Wraps :meth:`batch_scrape` with a supervisor that automatically
        retries on any crash (exception, KeyboardInterrupt, browser failure).
        Each retry resumes from the checkpoint — only pending and previously
        failed videos are re-scraped. The user never sees an unhandled error;
        the method keeps retrying until all videos succeed or ``max_retries``
        is exhausted.

        Requires a ``checkpoint`` path — without it, there is nothing to
        resume from.

        Args:
            urls_or_ids: List of YouTube URLs or video IDs.
            max_workers: Concurrent browser instances (default: config.max_workers).
            batch_delay: Delay between starting each task (default: config.batch_delay).
            progress_callback: Optional ``(index, total, video_id, status)`` callback.
            checkpoint: Path to checkpoint JSON file (required for resume).
            max_retries: Max retry attempts after a crash (default: 3).
            retry_delay: Seconds to wait before retrying (default: 5.0).

        Returns:
            A :class:`BatchResult` with all results accumulated across retries.

        Raises:
            ValueError: If ``checkpoint`` is not provided.

        Example::

            with YouTubeScraper(ScraperConfig(max_workers=4)) as scraper:
                batch = scraper.batch_scrape_resilient(
                    urls,
                    checkpoint="progress.json",
                    max_retries=5,
                    retry_delay=10.0,
                )
                # Even if the process crashes 3 times, it auto-resumes
                # and returns the complete result.
                print(f"Done: {batch.succeeded} ok, {batch.failed} failed")
        """
        if not checkpoint:
            raise ValueError("batch_scrape_resilient requires a checkpoint path")

        all_results: list[VideoResult] = []
        all_errors: list[BatchError] = []
        total = len(urls_or_ids)
        start_time = time.time()
        attempt = 0
        prev_succeeded = -1

        while attempt <= max_retries:
            attempt += 1
            try:
                logging.info("Resilient batch attempt %d/%d", attempt, max_retries + 1)
                if attempt > 1:
                    logging.info("Retrying failed videos from checkpoint...")
                    if retry_delay > 0:
                        time.sleep(retry_delay)

                batch = self.batch_scrape(
                    urls_or_ids,
                    max_workers=max_workers,
                    batch_delay=batch_delay,
                    progress_callback=progress_callback,
                    checkpoint=checkpoint,
                    retry_failed=(attempt > 1),  # Retry failed videos on re-attempts
                )

                # Merge results
                all_results = batch.results
                all_errors = batch.errors

                # If everything succeeded, we're done
                if batch.failed == 0:
                    break

                # If no progress was made this attempt, stop to avoid infinite loop
                # BUG FIX: compare against previous attempt's succeeded count
                if attempt > 1 and batch.succeeded == prev_succeeded:
                    logging.warning("No progress on attempt %d, stopping", attempt)
                    break
                prev_succeeded = batch.succeeded

            except KeyboardInterrupt:
                logging.warning("Interrupted on attempt %d, saving checkpoint and retrying...", attempt)
                if attempt > max_retries:
                    break
                if retry_delay > 0:
                    time.sleep(retry_delay)
                continue

            except Exception as exc:  # noqa: BLE001
                logging.warning("Crash on attempt %d: %s", attempt, exc)
                if attempt > max_retries:
                    # Load whatever we have from checkpoint
                    all_results, all_errors = self._load_checkpoint_results(checkpoint, urls_or_ids)
                    break
                if retry_delay > 0:
                    time.sleep(retry_delay)
                continue

        elapsed = time.time() - start_time
        return BatchResult(
            total=total,
            succeeded=len(all_results),
            failed=len(all_errors),
            results=all_results,
            errors=all_errors,
            elapsed_seconds=round(elapsed, 2),
        )

    @staticmethod
    def _load_checkpoint_results(
        checkpoint: str,
        urls_or_ids: list[str],
    ) -> tuple[list[VideoResult], list[BatchError]]:
        """Load results and errors from a checkpoint file."""
        results: list[VideoResult] = []
        errors: list[BatchError] = []
        cp_path = Path(checkpoint)
        if not cp_path.exists():
            return results, errors
        try:
            checkpoint_data = json.loads(cp_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return results, errors

        for url_or_id in urls_or_ids:
            entry = checkpoint_data.get(url_or_id)
            if not entry:
                continue
            if entry.get("status") == "ok" and "result" in entry:
                results.append(YouTubeScraper._deserialize_result(entry["result"]))
            elif entry.get("status") == "error":
                errors.append(BatchError(
                    url_or_id=url_or_id,
                    error_type=entry.get("error_type", "Unknown"),
                    error_message=entry.get("error_message", ""),
                ))
        return results, errors

    # -- Channel / Playlist discovery ------------------------------------

    def get_channel_video_ids(
        self,
        channel_url_or_id: str,
        max_videos: int = 50,
    ) -> list[str]:
        """Discover video IDs from a YouTube channel.

        Navigates to the channel's videos page and extracts video IDs from
        the page's initial data payload. No scrolling is performed — this
        captures the first page of videos (typically 30-50 videos).

        Args:
            channel_url_or_id: Channel URL (e.g. ``https://www.youtube.com/@handle``),
                channel ID (e.g. ``UCxxxx``), or ``@handle``.
            max_videos: Maximum number of video IDs to return.

        Returns:
            List of 11-character video IDs.

        Raises:
            InvalidVideoURLError: If the channel URL cannot be parsed.
            BrowserNotInitializedError: If not used as a context manager.
        """
        if self.driver is None:
            raise BrowserNotInitializedError("YouTubeScraper must be used as a context manager")

        # Normalize channel URL
        if channel_url_or_id.startswith("@"):
            videos_url = f"https://www.youtube.com/{channel_url_or_id}/videos"
        elif "youtube.com" in channel_url_or_id:
            base = channel_url_or_id.rstrip("/")
            if "/videos" not in base:
                base = base + "/videos"
            videos_url = base
        elif channel_url_or_id.startswith("UC"):
            videos_url = f"https://www.youtube.com/channel/{channel_url_or_id}/videos"
        else:
            videos_url = f"https://www.youtube.com/@{channel_url_or_id}/videos"

        html, _ = self._load_watch_html(videos_url)
        initial = extract_json_assignment(html, "ytInitialData") or {}

        # Extract video IDs from the channel page's renderers
        video_ids: list[str] = []
        seen: set[str] = set()

        # Look for videoId in various renderer types
        for vid_id in find_all_keys(initial, "videoId"):
            if isinstance(vid_id, str) and len(vid_id) == 11 and vid_id not in seen:
                seen.add(vid_id)
                video_ids.append(vid_id)
                if len(video_ids) >= max_videos:
                    break

        return video_ids

    def get_playlist_video_ids(
        self,
        playlist_url_or_id: str,
        max_videos: int = 100,
    ) -> list[str]:
        """Discover video IDs from a YouTube playlist.

        Navigates to the playlist page and extracts video IDs from the
        page's initial data payload.

        Args:
            playlist_url_or_id: Playlist URL (e.g.
                ``https://www.youtube.com/playlist?list=PLxxxx``) or
                bare playlist ID (e.g. ``PLxxxx``).
            max_videos: Maximum number of video IDs to return.

        Returns:
            List of 11-character video IDs.

        Raises:
            InvalidVideoURLError: If the playlist URL cannot be parsed.
            BrowserNotInitializedError: If not used as a context manager.
        """
        if self.driver is None:
            raise BrowserNotInitializedError("YouTubeScraper must be used as a context manager")

        # Normalize playlist URL
        if playlist_url_or_id.startswith("PL") or playlist_url_or_id.startswith("OL") or playlist_url_or_id.startswith("RD"):
            playlist_url = f"https://www.youtube.com/playlist?list={playlist_url_or_id}"
        elif "list=" in playlist_url_or_id:
            playlist_url = playlist_url_or_id
        else:
            playlist_url = f"https://www.youtube.com/playlist?list={playlist_url_or_id}"

        html, _ = self._load_watch_html(playlist_url)
        initial = extract_json_assignment(html, "ytInitialData") or {}

        video_ids: list[str] = []
        seen: set[str] = set()

        for vid_id in find_all_keys(initial, "videoId"):
            if isinstance(vid_id, str) and len(vid_id) == 11 and vid_id not in seen:
                seen.add(vid_id)
                video_ids.append(vid_id)
                if len(video_ids) >= max_videos:
                    break

        return video_ids

    def scrape_channel(
        self,
        channel_url_or_id: str,
        max_videos: int = 30,
        max_workers: int | None = None,
        batch_delay: float | None = None,
        checkpoint: str | None = None,
        progress_callback: Any = None,
    ) -> BatchResult:
        """Discover and scrape all videos from a YouTube channel.

        Combines :meth:`get_channel_video_ids` and :meth:`batch_scrape`
        in one call. Discovers video IDs from the channel, then scrapes
        each video concurrently.

        Args:
            channel_url_or_id: Channel URL, ID, or @handle.
            max_videos: Max videos to discover from the channel.
            max_workers: Concurrent browser instances.
            batch_delay: Delay between starting each task.
            checkpoint: Optional checkpoint path for crash recovery.
            progress_callback: Optional progress callback.

        Returns:
            A :class:`BatchResult` with all scraped videos.
        """
        video_ids = self.get_channel_video_ids(channel_url_or_id, max_videos)
        if not video_ids:
            return BatchResult(total=0)
        logging.info("Found %d videos on channel", len(video_ids))
        return self.batch_scrape(
            video_ids,
            max_workers=max_workers,
            batch_delay=batch_delay,
            checkpoint=checkpoint,
            progress_callback=progress_callback,
        )

    def scrape_playlist(
        self,
        playlist_url_or_id: str,
        max_videos: int = 100,
        max_workers: int | None = None,
        batch_delay: float | None = None,
        checkpoint: str | None = None,
        progress_callback: Any = None,
    ) -> BatchResult:
        """Discover and scrape all videos from a YouTube playlist.

        Combines :meth:`get_playlist_video_ids` and :meth:`batch_scrape`
        in one call.

        Args:
            playlist_url_or_id: Playlist URL or ID.
            max_videos: Max videos to discover from the playlist.
            max_workers: Concurrent browser instances.
            batch_delay: Delay between starting each task.
            checkpoint: Optional checkpoint path for crash recovery.
            progress_callback: Optional progress callback.

        Returns:
            A :class:`BatchResult` with all scraped videos.
        """
        video_ids = self.get_playlist_video_ids(playlist_url_or_id, max_videos)
        if not video_ids:
            return BatchResult(total=0)
        logging.info("Found %d videos in playlist", len(video_ids))
        return self.batch_scrape(
            video_ids,
            max_workers=max_workers,
            batch_delay=batch_delay,
            checkpoint=checkpoint,
            progress_callback=progress_callback,
        )

    @staticmethod
    def _deserialize_result(data: dict) -> VideoResult:
        """Reconstruct a VideoResult from a checkpoint dict (best-effort)."""
        from .models import (
            AccessStatus,
            DislikeData,
            Engagement,
            NetworkInfo,
            Summary,
            Transcript,
            VideoMetadata,
        )

        metadata = VideoMetadata(**data.get("metadata", {}))
        engagement_data = data.get("engagement", {})
        dislikes_data = engagement_data.pop("dislikes", None)
        dislikes = DislikeData(**dislikes_data) if dislikes_data else None
        engagement = Engagement(dislikes=dislikes, **engagement_data)
        transcript = Transcript(**data.get("transcript", {}))
        summary = Summary(**data.get("summary", {}))
        network_data = data.get("network", {})
        access_data = network_data.pop("access_status", {})
        access_status = AccessStatus(**access_data)
        network = NetworkInfo(access_status=access_status, **network_data)
        comments = [Comment(**c) for c in data.get("comments", [])]

        return VideoResult(
            video_id=data.get("video_id", ""),
            source_url=data.get("source_url", ""),
            metadata=metadata,
            engagement=engagement,
            transcript=transcript,
            summary=summary,
            comments=comments,
            network=network,
        )

    # -- Browser / network internals -------------------------------------

    def _build_driver(self) -> Any:
        """Create and configure a Selenium Chrome driver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ModuleNotFoundError as exc:
            raise SeleniumNotInstalledError(
                "Selenium is required to run the scraper. "
                "Install dependencies with `pip install yt-network-scraper[browser]`."
            ) from exc

        options = Options()
        if self.config.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--mute-audio")
        options.add_argument(f"--user-agent={self.config.user_agent}")
        options.add_argument("--window-size=1365,900")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        # Use Chromium binary if CHROME_BIN env var is set (e.g. in Docker)
        chrome_bin = os.environ.get("CHROME_BIN")
        if chrome_bin:
            options.binary_location = chrome_bin

        # Use explicit chromedriver path if CHROMEDRIVER_PATH env var is set
        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
        if chromedriver_path:
            from selenium.webdriver.chrome.service import Service
            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(self.config.timeout)
        driver.execute_cdp_cmd("Network.enable", {})
        return driver

    def _load_watch_html(self, url: str) -> tuple[str, list[dict[str, Any]]]:
        """Load the watch page and return ``(html, network_events)``.

        Retries on access-block pages up to ``max_page_retries`` times.
        """
        if self.driver is None:
            raise BrowserNotInitializedError(
                "YouTubeScraper must be used as a context manager."
            )

        html = ""
        collected_events: list[dict[str, Any]] = []

        for attempt in range(max(1, self.config.max_page_retries + 1)):
            if attempt:
                self._polite_sleep(multiplier=attempt + 1)
            self.driver.get(url)
            time.sleep(min(5, max(2, self.config.timeout // 5)))

            html, events = self._read_watch_html_from_network(url)
            collected_events.extend(events)
            block = detect_access_block(html)
            if not block["blocked"]:
                return html, collected_events

        logger.warning("YouTube returned an access challenge after %d attempts", self.config.max_page_retries + 1)
        return html, collected_events

    def _read_watch_html_from_network(self, url: str) -> tuple[str, list[dict[str, Any]]]:
        """Read the watch-page HTML from captured network response bodies.

        Falls back to a direct HTTP GET if the network body has expired.
        This fallback is still network-based and does not inspect the DOM.
        """
        if self.driver is None:
            raise BrowserNotInitializedError("YouTubeScraper must be used as a context manager.")

        logs = self.driver.get_log("performance")
        events: list[dict[str, Any]] = []
        document_request_ids: list[str] = []

        for raw in logs:
            try:
                message = json.loads(raw["message"])["message"]
            except (KeyError, json.JSONDecodeError):
                continue
            events.append(message)
            if message.get("method") != "Network.responseReceived":
                continue
            params = message.get("params", {})
            response = params.get("response", {})
            response_url = response.get("url", "")
            if params.get("type") == "Document" and "youtube.com/watch" in response_url:
                document_request_ids.append(params["requestId"])

        for request_id in reversed(document_request_ids):
            try:
                body = self.driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
            except Exception:
                continue
            html = body.get("body", "")
            if "ytInitialPlayerResponse" in html:
                return html, events

        self._polite_sleep()
        response = self.session.get(url, timeout=self.config.timeout)
        response.raise_for_status()
        return response.text, events

    def _polite_sleep(self, multiplier: float = 1.0) -> None:
        """Sleep for a configurable delay with jitter to be polite to YouTube."""
        if self.config.request_delay <= 0:
            return
        jitter = random.uniform(0.25, 0.9)
        time.sleep((self.config.request_delay + jitter) * multiplier)

    def _trigger_transcript_panel_from_network(self) -> Transcript:
        """Click the transcript button in the browser and capture the panel response.

        This is a fallback when the timedtext URL is unavailable.  It
        interacts with the page UI to open the transcript panel, then
        captures the ``get_panel`` network response.
        """
        if self.driver is None:
            return Transcript(available=False)

        try:
            from selenium.webdriver.common.by import By
        except ModuleNotFoundError:
            return Transcript(available=False)

        try:
            self.driver.get_log("performance")
        except Exception:
            pass

        try:
            more_buttons = self.driver.find_elements(
                By.XPATH,
                "//*[self::tp-yt-paper-button or self::button or @role='button']"
                "[contains(., '...more') or contains(., 'more')]",
            )
            for button in more_buttons:
                if button.is_displayed():
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();",
                        button,
                    )
                    time.sleep(1)
                    break
        except Exception:
            pass

        try:
            transcript_buttons = self.driver.find_elements(
                By.XPATH,
                "//button[@aria-label='Show transcript'] | //*[@role='button' and @aria-label='Show transcript']",
            )
            if transcript_buttons:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();",
                    transcript_buttons[0],
                )
        except Exception:
            return Transcript(available=False)

        time.sleep(5)
        response_ids: list[str] = []
        try:
            logs = self.driver.get_log("performance")
        except Exception:
            logs = []

        for raw in logs:
            try:
                message = json.loads(raw["message"])["message"]
            except (KeyError, json.JSONDecodeError):
                continue
            if message.get("method") != "Network.responseReceived":
                continue
            params = message.get("params", {})
            url = params.get("response", {}).get("url", "")
            if "youtubei/v1/get_panel" in url:
                response_ids.append(params.get("requestId", ""))

        from .parsing import parse_panel_transcript_segments

        for request_id in reversed([rid for rid in response_ids if rid]):
            try:
                body = self.driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                data = json.loads(body.get("body", ""))
            except Exception:
                continue

            segments = parse_panel_transcript_segments(data)
            if segments:
                return Transcript(
                    available=True,
                    segments=segments,
                    text=" ".join(seg.text for seg in segments),
                    source="browser_network_get_panel",
                )

        return Transcript(available=False)
