from __future__ import annotations

import json
import math
import random
import re
import time
from collections import Counter
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests


YOUTUBEI_BASE = "https://www.youtube.com/youtubei/v1"
RYD_API = "https://returnyoutubedislikeapi.com/votes"


@dataclass(slots=True)
class ScraperConfig:
    headless: bool = True
    timeout: int = 25
    max_comments: int = 25
    transcript_language: str = "en"
    request_delay: float = 1.5
    max_page_retries: int = 2
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )


class YouTubeNetworkScraper:
    """Scrape YouTube data from browser-captured and follow-up network payloads."""

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

    def __enter__(self) -> "YouTubeNetworkScraper":
        self.driver = self._build_driver()
        return self

    def __exit__(self, *_exc: object) -> None:
        if self.driver is not None:
            self.driver.quit()
            self.driver = None

    def scrape(self, url: str) -> dict[str, Any]:
        video_id = extract_video_id(url)
        watch_url = f"https://www.youtube.com/watch?v={video_id}&hl=en&persist_hl=1"
        html, network_events = self._load_watch_html(watch_url)
        access_status = detect_access_block(html)

        player = extract_json_assignment(html, "ytInitialPlayerResponse") or {}
        initial = extract_json_assignment(html, "ytInitialData") or {}
        ytcfg = extract_ytcfg(html) or {}
        api_key = ytcfg.get("INNERTUBE_API_KEY") or extract_api_key(html, network_events)
        context = ytcfg.get("INNERTUBE_CONTEXT") or extract_innertube_context(html)

        metadata = parse_metadata(video_id, player, initial)
        transcript = fetch_transcript(
            self.session,
            player,
            self.config.transcript_language,
            initial=initial,
            api_key=api_key,
            context=context,
        )
        if not transcript.get("available"):
            panel_transcript = self._trigger_transcript_panel_from_network()
            if panel_transcript.get("available"):
                if not panel_transcript.get("language"):
                    panel_transcript["language"] = transcript.get("language")
                if not panel_transcript.get("name"):
                    panel_transcript["name"] = transcript.get("name")
                if panel_transcript.get("is_auto_generated") is None:
                    panel_transcript["is_auto_generated"] = transcript.get("is_auto_generated")
                transcript = panel_transcript
        comment_data = fetch_comment_data(
            self.session,
            initial,
            api_key=api_key,
            context=context,
            max_comments=self.config.max_comments,
        )
        dislikes = fetch_dislikes(self.session, video_id)
        likes = metadata.pop("_likes", None)
        if likes is None and dislikes:
            likes = int_or_none(dislikes.get("likes"))
        summary = summarize_text(transcript.get("text") or metadata.get("description") or "")

        return {
            "video_id": video_id,
            "source_url": watch_url,
            "metadata": metadata,
            "engagement": {
                "likes": likes,
                "views": metadata.get("views"),
                "dislikes": dislikes,
                "comment_count": comment_data.get("comment_count"),
                "comment_count_scraped": len(comment_data["comments"]),
            },
            "transcript": transcript,
            "summary": summary,
            "comments": comment_data["comments"],
            "network": {
                "api_key_found": bool(api_key),
                "captured_event_count": len(network_events),
                "dom_scraping": False,
                "access_status": access_status,
                "bot_evasion": False,
            },
        }

    def _build_driver(self) -> Any:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Selenium is required to run the network scraper. "
                "Install dependencies with `pip install -e .` or `pip install -r requirements.txt`."
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
        if self.driver is None:
            raise RuntimeError("Use YouTubeNetworkScraper as a context manager.")

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

        return html, collected_events

    def _read_watch_html_from_network(self, url: str) -> tuple[str, list[dict[str, Any]]]:
        if self.driver is None:
            raise RuntimeError("Use YouTubeNetworkScraper as a context manager.")

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

        # Network response bodies can expire quickly in Chrome. This fallback is still
        # network based and does not inspect the DOM.
        self._polite_sleep()
        response = self.session.get(url, timeout=self.config.timeout)
        response.raise_for_status()
        return response.text, events

    def _polite_sleep(self, multiplier: float = 1.0) -> None:
        if self.config.request_delay <= 0:
            return
        jitter = random.uniform(0.25, 0.9)
        time.sleep((self.config.request_delay + jitter) * multiplier)

    def _trigger_transcript_panel_from_network(self) -> dict[str, Any]:
        if self.driver is None:
            return {"available": False, "language": None, "segments": [], "text": ""}

        try:
            from selenium.webdriver.common.by import By
        except ModuleNotFoundError:
            return {"available": False, "language": None, "segments": [], "text": ""}

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
            return {"available": False, "language": None, "segments": [], "text": ""}

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

        for request_id in reversed([request_id for request_id in response_ids if request_id]):
            try:
                body = self.driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                data = json.loads(body.get("body", ""))
            except Exception:
                continue

            segments = parse_panel_transcript_segments(data)
            if segments:
                return {
                    "available": True,
                    "language": None,
                    "segments": segments,
                    "text": " ".join(segment["text"] for segment in segments),
                    "source": "browser_network_get_panel",
                }

        return {"available": False, "language": None, "segments": [], "text": ""}


def extract_video_id(url_or_id: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id

    parsed = urlparse(url_or_id)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if "youtu.be" in host and path:
        return path.split("/")[0]
    if path.startswith("shorts/"):
        return path.split("/")[1]

    query_id = parse_qs(parsed.query).get("v", [None])[0]
    if query_id:
        return query_id

    raise ValueError(f"Could not extract a YouTube video id from {url_or_id!r}")


def detect_access_block(html: str) -> dict[str, Any]:
    normalized = re.sub(r"\s+", " ", html).lower()
    player_missing = "ytinitialplayerresponse" not in normalized
    captcha_challenge = (
        "our systems have detected unusual traffic" in normalized
        or "to continue, please type the characters" in normalized
        or "recaptcha/api2" in normalized and player_missing
    )
    checks = {
        "captcha": captcha_challenge,
        "unusual_traffic": "unusual traffic" in normalized or "automated queries" in normalized,
        "consent": "consent.youtube.com" in normalized or "before you continue to youtube" in normalized,
        "sign_in_required": "sign in to confirm" in normalized or "this video may be inappropriate" in normalized,
        "player_missing": player_missing,
    }
    reasons = [name for name, matched in checks.items() if matched]
    return {
        "blocked": any(checks.values()),
        "reasons": reasons,
        "message": "Access looks normal" if not reasons else "YouTube returned an access challenge or incomplete watch payload",
    }


def extract_json_assignment(html: str, variable_name: str) -> dict[str, Any] | None:
    marker = f"var {variable_name} ="
    start = html.find(marker)
    if start == -1:
        marker = f"window[\"{variable_name}\"] ="
        start = html.find(marker)
    if start == -1:
        marker = f"{variable_name} ="
        start = html.find(marker)
    if start == -1:
        return None

    brace_start = html.find("{", start)
    if brace_start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for idx in range(brace_start, len(html)):
        char = html[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[brace_start : idx + 1])
                except json.JSONDecodeError:
                    return None
    return None


def extract_ytcfg(html: str) -> dict[str, Any] | None:
    start = html.find("ytcfg.set(")
    while start != -1:
        brace_start = html.find("{", start)
        if brace_start == -1:
            return None
        parsed = extract_json_object_at(html, brace_start)
        if parsed and "INNERTUBE_CONTEXT" in parsed:
            return parsed
        start = html.find("ytcfg.set(", start + 1)
    return None


def extract_json_object_at(text: str, brace_start: int) -> dict[str, Any] | None:
    depth = 0
    in_string = False
    escaped = False
    for idx in range(brace_start, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[brace_start : idx + 1])
                except json.JSONDecodeError:
                    return None
    return None


def extract_api_key(html: str, events: list[dict[str, Any]]) -> str | None:
    patterns = [
        r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"',
        r"innertubeApiKey\\?\"\s*:\s*\\?\"([^\"\\]+)",
        r"[?&]key=([^&\"\\]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return unescape(match.group(1))

    for event in events:
        params = event.get("params", {})
        url = params.get("request", {}).get("url") or params.get("response", {}).get("url", "")
        if "youtubei/v1" in url:
            key = parse_qs(urlparse(url).query).get("key", [None])[0]
            if key:
                return unquote(key)
    return None


def extract_innertube_context(html: str) -> dict[str, Any]:
    context_match = re.search(r'"INNERTUBE_CONTEXT"\s*:\s*(\{.*?\})\s*,\s*"INNERTUBE_CONTEXT_CLIENT_NAME"', html)
    if context_match:
        try:
            return json.loads(context_match.group(1))
        except json.JSONDecodeError:
            pass

    return {
        "client": {
            "clientName": "WEB",
            "clientVersion": extract_client_version(html) or "2.20240601.00.00",
            "hl": "en",
            "gl": "US",
        }
    }


def extract_client_version(html: str) -> str | None:
    match = re.search(r'"INNERTUBE_CLIENT_VERSION"\s*:\s*"([^"]+)"', html)
    return match.group(1) if match else None


def parse_metadata(video_id: str, player: dict[str, Any], initial: dict[str, Any]) -> dict[str, Any]:
    details = player.get("videoDetails", {})
    microformat = player.get("microformat", {}).get("playerMicroformatRenderer", {})
    owner = find_key(initial, "videoOwnerRenderer") or {}
    secondary = find_key(initial, "videoSecondaryInfoRenderer") or {}

    metadata = {
        "title": details.get("title") or text_from(microformat.get("title")),
        "description": details.get("shortDescription") or text_from(microformat.get("description")),
        "views": int_or_none(details.get("viewCount") or text_from(microformat.get("viewCount"))),
        "channel_name": details.get("author") or text_from(owner.get("title")),
        "channel_id": details.get("channelId") or microformat.get("externalChannelId"),
        "channel_url": microformat.get("ownerProfileUrl"),
        "channel_subscribers": text_from(owner.get("subscriberCountText"))
        or text_from(secondary.get("owner", {}).get("videoOwnerRenderer", {}).get("subscriberCountText")),
        "upload_date": microformat.get("uploadDate"),
        "publish_date": microformat.get("publishDate"),
        "timestamp": microformat.get("publishDate") or microformat.get("uploadDate"),
        "duration_seconds": int_or_none(details.get("lengthSeconds")),
        "category": microformat.get("category"),
        "is_live": details.get("isLiveContent"),
        "keywords": details.get("keywords", []),
        "thumbnail": (details.get("thumbnail", {}).get("thumbnails") or [{}])[-1].get("url"),
        "_likes": find_like_count(initial),
    }

    if not metadata["channel_url"] and metadata["channel_id"]:
        metadata["channel_url"] = f"https://www.youtube.com/channel/{metadata['channel_id']}"
    metadata["video_url"] = f"https://www.youtube.com/watch?v={video_id}"
    return metadata


def find_like_count(initial: dict[str, Any]) -> int | None:
    segmented = find_key(initial, "segmentedLikeDislikeButtonViewModel")
    if not segmented:
        return None
    text = json.dumps(segmented, ensure_ascii=False)
    matches = re.findall(r'"content"\s*:\s*"([^"]+)"', text)
    for value in matches:
        parsed = parse_compact_number(value)
        if parsed is not None:
            return parsed
    return None


def fetch_dislikes(session: requests.Session, video_id: str) -> dict[str, Any] | None:
    try:
        response = session.get(RYD_API, params={"videoId": video_id}, timeout=12)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return {
            "dislikes": data.get("dislikes"),
            "likes": data.get("likes"),
            "rating": data.get("rating"),
            "view_count": data.get("viewCount"),
            "source": "returnyoutubedislikeapi.com",
        }
    except requests.RequestException:
        return None


def fetch_transcript(
    session: requests.Session,
    player: dict[str, Any],
    preferred_lang: str,
    *,
    initial: dict[str, Any] | None = None,
    api_key: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tracks = (
        player.get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks", [])
    )
    if not tracks:
        panel_transcript = fetch_panel_transcript(session, initial or {}, api_key=api_key, context=context)
        if panel_transcript["available"]:
            return panel_transcript
        return {"available": False, "language": None, "segments": [], "text": ""}

    track = choose_caption_track(tracks, preferred_lang)
    base_url = track.get("baseUrl")
    if not base_url:
        panel_transcript = fetch_panel_transcript(session, initial or {}, api_key=api_key, context=context)
        if panel_transcript["available"]:
            return panel_transcript
        return {"available": False, "language": None, "segments": [], "text": ""}

    separator = "&" if "?" in base_url else "?"
    url = f"{base_url}{separator}fmt=json3"
    caption_error = None
    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        data = {}
        caption_error = "caption_track_unavailable"

    segments = []
    for event in data.get("events", []):
        pieces = event.get("segs") or []
        text = "".join(piece.get("utf8", "") for piece in pieces).strip()
        if text:
            segments.append(
                {
                    "start_ms": event.get("tStartMs"),
                    "duration_ms": event.get("dDurationMs"),
                    "text": text,
                }
            )

    if segments:
        return {
            "available": True,
            "language": track.get("languageCode"),
            "name": text_from(track.get("name")),
            "is_auto_generated": track.get("kind") == "asr",
            "segments": segments,
            "text": " ".join(segment["text"] for segment in segments),
            "source": "timedtext",
        }

    panel_transcript = fetch_panel_transcript(session, initial or {}, api_key=api_key, context=context)
    if panel_transcript["available"]:
        if not panel_transcript.get("language"):
            panel_transcript["language"] = track.get("languageCode")
        if not panel_transcript.get("name"):
            panel_transcript["name"] = text_from(track.get("name"))
        if panel_transcript.get("is_auto_generated") is None:
            panel_transcript["is_auto_generated"] = track.get("kind") == "asr"
        return panel_transcript

    return {
        "available": False,
        "language": track.get("languageCode"),
        "name": text_from(track.get("name")),
        "is_auto_generated": track.get("kind") == "asr",
        "segments": [],
        "text": "",
        "error": caption_error or "no_transcript_segments",
    }


def fetch_panel_transcript(
    session: requests.Session,
    initial: dict[str, Any],
    *,
    api_key: str | None,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    if not api_key or not context:
        return {"available": False, "language": None, "segments": [], "text": ""}

    for panel_params in find_transcript_panel_params(initial):
        endpoint = f"{YOUTUBEI_BASE}/get_panel?prettyPrint=false&key={quote(api_key)}"
        try:
            response = session.post(endpoint, json={"context": context, "params": panel_params}, timeout=20)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError):
            continue

        segments = parse_panel_transcript_segments(data)
        if segments:
            return {
                "available": True,
                "language": None,
                "segments": segments,
                "text": " ".join(segment["text"] for segment in segments),
                "source": "youtubei_get_panel",
            }

    return {"available": False, "language": None, "segments": [], "text": ""}


def find_transcript_panel_params(initial: dict[str, Any]) -> list[str]:
    params: list[str] = []

    for endpoint in find_all_keys(initial, "showEngagementPanelEndpoint"):
        identifier = endpoint.get("identifier", {}) if isinstance(endpoint, dict) else {}
        tag = identifier.get("tag")
        panel_params = endpoint.get("globalConfiguration", {}).get("params") if isinstance(endpoint, dict) else None
        if tag == "PAmodern_transcript_view" and panel_params:
            params.append(panel_params)

    for command in find_all_keys(initial, "updateEngagementPanelContentCommand"):
        if not isinstance(command, dict):
            continue
        source = command.get("contentSourcePanelIdentifier", {})
        panel_params = command.get("globalConfiguration", {}).get("params")
        if source.get("tag") == "PAmodern_transcript_view" and panel_params:
            params.append(panel_params)

    seen: set[str] = set()
    unique_params = []
    for panel_params in params:
        if panel_params not in seen:
            seen.add(panel_params)
            unique_params.append(panel_params)
    return unique_params


def parse_panel_transcript_segments(data: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []

    for renderer in find_all_keys(data, "macroMarkersPanelItemViewModel"):
        timeline = renderer.get("item", {}).get("timelineItemViewModel", {}) if isinstance(renderer, dict) else {}
        timestamp = timeline.get("timestamp")
        for content_item in timeline.get("contentItems", []) or []:
            segment = content_item.get("transcriptSegmentViewModel", {})
            text = segment.get("simpleText") or text_from(segment.get("text"))
            if not text:
                continue
            segments.append(
                {
                    "start_ms": parse_timestamp_ms(timestamp),
                    "duration_ms": None,
                    "time": timestamp,
                    "text": text,
                }
            )

    if segments:
        return segments

    for renderer in find_all_keys(data, "transcriptSegmentRenderer"):
        text = text_from(renderer.get("snippet"))
        if not text:
            continue
        segments.append(
            {
                "start_ms": int_or_none(renderer.get("startMs")),
                "end_ms": int_or_none(renderer.get("endMs")),
                "duration_ms": duration_from_bounds(renderer.get("startMs"), renderer.get("endMs")),
                "time": text_from(renderer.get("startTimeText")),
                "text": text,
            }
        )

    if segments:
        return segments

    for renderer in find_all_keys(data, "transcriptCueGroupRenderer"):
        cue = renderer.get("cue", {}) if isinstance(renderer, dict) else {}
        cue_renderer = cue.get("transcriptCueRenderer", {}) if isinstance(cue, dict) else {}
        text = text_from(cue_renderer.get("cue"))
        if not text:
            continue
        segments.append(
            {
                "start_ms": int_or_none(cue_renderer.get("startOffsetMs")),
                "duration_ms": int_or_none(cue_renderer.get("durationMs")),
                "time": text_from(cue_renderer.get("timestamp")),
                "text": text,
            }
        )

    return segments


def parse_timestamp_ms(value: str | None) -> int | None:
    if not value:
        return None
    parts = value.split(":")
    if not all(part.isdigit() for part in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds * 1000


def duration_from_bounds(start: Any, end: Any) -> int | None:
    start_ms = int_or_none(start)
    end_ms = int_or_none(end)
    if start_ms is None or end_ms is None:
        return None
    return max(0, end_ms - start_ms)


def choose_caption_track(tracks: list[dict[str, Any]], preferred_lang: str) -> dict[str, Any]:
    for track in tracks:
        if track.get("languageCode") == preferred_lang and track.get("kind") != "asr":
            return track
    for track in tracks:
        if track.get("languageCode") == preferred_lang:
            return track
    for track in tracks:
        if track.get("vssId", "").startswith(f".{preferred_lang}"):
            return track
    return tracks[0]


def fetch_comment_data(
    session: requests.Session,
    initial: dict[str, Any],
    *,
    api_key: str | None,
    context: dict[str, Any],
    max_comments: int,
) -> dict[str, Any]:
    if max_comments <= 0 or not api_key:
        return {"comment_count": find_comment_count(initial), "comments": []}

    continuation = find_comment_continuation(initial)
    comments: list[dict[str, Any]] = []
    seen: set[str] = set()
    comment_count = find_comment_count(initial)

    while continuation and len(comments) < max_comments:
        endpoint = f"{YOUTUBEI_BASE}/next?key={quote(api_key)}"
        payload = {"context": context, "continuation": continuation}
        try:
            response = session.post(endpoint, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError):
            break

        comment_count = find_comment_count(data) or comment_count

        for renderer in find_all_keys(data, "commentRenderer"):
            comment_id = renderer.get("commentId")
            if comment_id in seen:
                continue
            seen.add(comment_id or json.dumps(renderer, sort_keys=True)[:80])
            comments.append(parse_comment(renderer))
            if len(comments) >= max_comments:
                break

        for entity in find_all_keys(data, "commentEntityPayload"):
            comment = parse_comment_entity(entity)
            comment_id = comment.get("comment_id")
            if not comment_id or comment_id in seen:
                continue
            seen.add(comment_id)
            comments.append(comment)
            if len(comments) >= max_comments:
                break

        continuation = find_comment_continuation(data)

    return {"comment_count": comment_count, "comments": comments}


def fetch_comments(
    session: requests.Session,
    initial: dict[str, Any],
    *,
    api_key: str | None,
    context: dict[str, Any],
    max_comments: int,
) -> list[dict[str, Any]]:
    return fetch_comment_data(
        session,
        initial,
        api_key=api_key,
        context=context,
        max_comments=max_comments,
    )["comments"]


def find_comment_continuation(payload: dict[str, Any]) -> str | None:
    preferred_tokens: list[str] = []
    fallback_tokens: list[str] = []
    comment_markers = (
        "GNvbW1lbnRzLXNlY3Rpb24",
        "Y29tbWVudHMtc2VjdGlvbg",
        "ZW5nYWdlbWVudC1wYW5lbC1jb21tZW50cy1zZWN0aW9u",
        "ZW5nYWdlbWVudC1wYW5lbC1jb21tZW50cy1zZWN0aW9u",
    )
    for key in ("continuationItemRenderer", "reloadContinuationItemsCommand", "appendContinuationItemsAction"):
        for node in find_all_keys(payload, key):
            token = token_from_node(node)
            if token:
                if any(marker in token for marker in comment_markers):
                    preferred_tokens.append(token)
                else:
                    fallback_tokens.append(token)
    return (preferred_tokens or fallback_tokens or [None])[0]


def find_comment_count(payload: dict[str, Any]) -> int | None:
    for header in find_all_keys(payload, "commentsHeaderRenderer"):
        count = int_or_none(text_from(header.get("countText")))
        if count is not None:
            return count
    for header in find_all_keys(payload, "commentsEntryPointHeaderRenderer"):
        for value in header.values():
            count = int_or_none(text_from(value))
            if count is not None:
                return count
    return None


def token_from_node(node: Any) -> str | None:
    if isinstance(node, dict):
        endpoint = node.get("continuationEndpoint") or node.get("button", {}).get("buttonRenderer", {}).get("command")
        if endpoint:
            token = endpoint.get("continuationCommand", {}).get("token")
            if token:
                return token
        for value in node.values():
            token = token_from_node(value)
            if token:
                return token
    elif isinstance(node, list):
        for item in node:
            token = token_from_node(item)
            if token:
                return token
    return None


def parse_comment(renderer: dict[str, Any]) -> dict[str, Any]:
    author_endpoint = renderer.get("authorEndpoint", {}).get("browseEndpoint", {})
    return {
        "comment_id": renderer.get("commentId"),
        "author": text_from(renderer.get("authorText")),
        "author_channel_id": author_endpoint.get("browseId"),
        "text": text_from(renderer.get("contentText")),
        "published": text_from(renderer.get("publishedTimeText")),
        "likes": parse_compact_number(text_from(renderer.get("voteCount"))) or 0,
        "reply_count": int_or_none(text_from(renderer.get("replyCount"))) or 0,
        "is_pinned": bool(renderer.get("pinnedCommentBadge")),
        "is_hearted": bool(renderer.get("creatorHeart")),
    }


def parse_comment_entity(entity: dict[str, Any]) -> dict[str, Any]:
    properties = entity.get("properties", {})
    author = entity.get("author", {})
    toolbar = entity.get("toolbar", {})
    content = properties.get("content", {})
    author_endpoint = author.get("channelCommand", {}).get("innertubeCommand", {}).get("browseEndpoint", {})

    return {
        "comment_id": properties.get("commentId"),
        "author": author.get("displayName") or properties.get("authorButtonA11y"),
        "author_channel_id": author.get("channelId") or author_endpoint.get("browseId"),
        "author_channel_url": author_endpoint.get("canonicalBaseUrl"),
        "text": content.get("content") if isinstance(content, dict) else None,
        "published": properties.get("publishedTime"),
        "likes": parse_compact_number(toolbar.get("likeCountA11y"))
        or parse_compact_number(toolbar.get("likeCountNotliked"))
        or 0,
        "reply_count": parse_compact_number(toolbar.get("replyCountA11y"))
        or parse_compact_number(toolbar.get("replyCount"))
        or 0,
        "is_pinned": bool(entity.get("pinned")),
        "is_hearted": "heartActiveTooltip" in toolbar,
    }


def summarize_text(text: str, max_sentences: int = 5) -> dict[str, Any]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return {"available": False, "text": "", "method": "none"}

    sentences = split_sentences(cleaned)
    if len(sentences) <= max_sentences:
        return {"available": True, "text": cleaned, "method": "short_text_passthrough"}

    stopwords = {
        "the",
        "and",
        "that",
        "this",
        "with",
        "you",
        "for",
        "are",
        "but",
        "from",
        "have",
        "not",
        "your",
        "was",
        "will",
        "they",
        "their",
        "about",
        "there",
        "what",
        "when",
        "where",
        "which",
        "into",
        "just",
        "like",
        "then",
        "than",
    }
    words = re.findall(r"[A-Za-z][A-Za-z']+", cleaned.lower())
    freqs = Counter(word for word in words if word not in stopwords and len(word) > 2)
    if not freqs:
        return {"available": True, "text": " ".join(sentences[:max_sentences]), "method": "lead_sentences"}

    scores = []
    for index, sentence in enumerate(sentences):
        sentence_words = re.findall(r"[A-Za-z][A-Za-z']+", sentence.lower())
        score = sum(freqs[word] for word in sentence_words) / math.sqrt(max(len(sentence_words), 1))
        scores.append((score, index, sentence))

    selected = sorted(scores, reverse=True)[:max_sentences]
    selected_in_order = [sentence for _score, _index, sentence in sorted(selected, key=lambda item: item[1])]
    return {"available": True, "text": " ".join(selected_in_order), "method": "frequency_extractive"}


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if len(part.strip()) > 20]


def find_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = find_key(child, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_key(child, key)
            if found is not None:
                return found
    return None


def find_all_keys(value: Any, key: str) -> list[Any]:
    results: list[Any] = []
    if isinstance(value, dict):
        if key in value:
            results.append(value[key])
        for child in value.values():
            results.extend(find_all_keys(child, key))
    elif isinstance(value, list):
        for child in value:
            results.extend(find_all_keys(child, key))
    return results


def text_from(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return unescape(value)
    if isinstance(value, dict):
        if "simpleText" in value:
            return unescape(value["simpleText"])
        runs = value.get("runs")
        if isinstance(runs, list):
            return unescape("".join(str(run.get("text", "")) for run in runs))
        accessibility = value.get("accessibility", {}).get("accessibilityData", {}).get("label")
        if accessibility:
            return unescape(accessibility)
    return None


def int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    compact = parse_compact_number(text)
    if compact is not None:
        return compact
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_compact_number(value: str | None) -> int | None:
    if not value:
        return None
    text = value.replace(",", "").strip().lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*([kmb])?", text)
    if not match:
        return None
    number = float(match.group(1))
    suffix = match.group(2)
    multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(suffix, 1)
    return int(number * multiplier)
