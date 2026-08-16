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
import random
import time
from dataclasses import dataclass
from typing import Any

import requests

from .exceptions import (
    AccessBlockedException,
    BrowserNotInitializedError,
    InvalidVideoURLError,
    SeleniumNotInstalledError,
)
from .models import (
    AccessStatus,
    Comment,
    DislikeData,
    Engagement,
    NetworkInfo,
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
from .utils import detect_access_block, extract_video_id, int_or_none, summarize_text

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
    """

    headless: bool = True
    timeout: int = 25
    max_comments: int = 25
    transcript_language: str = "en"
    request_delay: float = 1.5
    max_page_retries: int = 2
    user_agent: str = DEFAULT_USER_AGENT


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
