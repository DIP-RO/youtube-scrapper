"""YouTube payload extraction and parsing functions.

These functions operate on the JSON payloads that YouTube embeds in
watch-page HTML (``ytInitialPlayerResponse``, ``ytInitialData``,
``ytcfg``) and on responses from the innertube API.
"""

from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import parse_qs, quote, unquote, urlparse

from typing import Any

from .models import Comment, TranscriptSegment
from .utils import (
    duration_from_bounds,
    find_all_keys,
    find_key,
    int_or_none,
    parse_compact_number,
    parse_timestamp_ms,
    text_from,
)


# ---------------------------------------------------------------------------
# JSON extraction from HTML
# ---------------------------------------------------------------------------

def extract_json_assignment(html: str, variable_name: str) -> dict[str, Any] | None:
    """Extract a JSON object assigned to *variable_name* in HTML source.

    Handles ``var X =``, ``window["X"] =``, and ``X =`` assignment styles.
    Uses brace-depth tracking to find the matching closing brace.
    """
    marker = f"var {variable_name} ="
    start = html.find(marker)
    if start == -1:
        marker = f'window["{variable_name}"] ='
        start = html.find(marker)
    if start == -1:
        marker = f"{variable_name} ="
        start = html.find(marker)
    if start == -1:
        return None

    brace_start = html.find("{", start)
    if brace_start == -1:
        return None

    return _extract_balanced_json(html, brace_start)


def extract_ytcfg(html: str) -> dict[str, Any] | None:
    """Extract the ``ytcfg.set(...)`` object that contains ``INNERTUBE_CONTEXT``."""
    start = html.find("ytcfg.set(")
    while start != -1:
        brace_start = html.find("{", start)
        if brace_start == -1:
            return None
        parsed = _extract_balanced_json(html, brace_start)
        if parsed and "INNERTUBE_CONTEXT" in parsed:
            return parsed
        start = html.find("ytcfg.set(", start + 1)
    return None


def _extract_balanced_json(text: str, brace_start: int) -> dict[str, Any] | None:
    """Parse a JSON object starting at *brace_start* using brace-depth tracking."""
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


# ---------------------------------------------------------------------------
# Innertube API key / context extraction
# ---------------------------------------------------------------------------

def extract_api_key(html: str, events: list[dict[str, Any]]) -> str | None:
    """Extract the public innertube API key from HTML or captured network events.

    The key is embedded in every watch page YouTube serves and is not a
    private credential.
    """
    patterns = [
        r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"',
        r'innertubeApiKey\\?"\s*:\s*\\?"([^"\\]+)',
        r'[?&]key=([^&"\\]+)',
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
    """Extract or reconstruct the innertube context object."""
    context_match = re.search(
        r'"INNERTUBE_CONTEXT"\s*:\s*(\{.*?\})\s*,\s*"INNERTUBE_CONTEXT_CLIENT_NAME"',
        html,
    )
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
    """Extract the innertube client version from HTML."""
    match = re.search(r'"INNERTUBE_CLIENT_VERSION"\s*:\s*"([^"]+)"', html)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Metadata parsing
# ---------------------------------------------------------------------------

def parse_metadata(video_id: str, player: dict[str, Any], initial: dict[str, Any]) -> dict[str, Any]:
    """Parse video metadata from the player response and initial data payloads."""
    details = player.get("videoDetails", {})
    microformat = player.get("microformat", {}).get("playerMicroformatRenderer", {})
    owner = find_key(initial, "videoOwnerRenderer") or {}
    secondary = find_key(initial, "videoSecondaryInfoRenderer") or {}

    channel_id = details.get("channelId") or microformat.get("externalChannelId")
    channel_url = microformat.get("ownerProfileUrl")
    if not channel_url and channel_id:
        channel_url = f"https://www.youtube.com/channel/{channel_id}"

    metadata = {
        "title": details.get("title") or text_from(microformat.get("title")),
        "description": details.get("shortDescription") or text_from(microformat.get("description")),
        "views": int_or_none(details.get("viewCount") or text_from(microformat.get("viewCount"))),
        "channel_name": details.get("author") or text_from(owner.get("title")),
        "channel_id": channel_id,
        "channel_url": channel_url,
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
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "_likes": find_like_count(initial),
    }
    return metadata


def find_like_count(initial: dict[str, Any]) -> int | None:
    """Extract the like count from the segmented like/dislike button view model."""
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


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------

def choose_caption_track(tracks: list[dict[str, Any]], preferred_lang: str) -> dict[str, Any]:
    """Select the best caption track for *preferred_lang*."""
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


def parse_panel_transcript_segments(data: dict[str, Any]) -> list[TranscriptSegment]:
    """Parse transcript segments from a ``get_panel`` API response.

    Supports three segment formats that YouTube has used:
    ``macroMarkersPanelItemViewModel``, ``transcriptSegmentRenderer``,
    and ``transcriptCueGroupRenderer``.
    """
    segments: list[TranscriptSegment] = []

    for renderer in find_all_keys(data, "macroMarkersPanelItemViewModel"):
        timeline = renderer.get("item", {}).get("timelineItemViewModel", {}) if isinstance(renderer, dict) else {}
        timestamp = timeline.get("timestamp")
        for content_item in timeline.get("contentItems", []) or []:
            segment = content_item.get("transcriptSegmentViewModel", {})
            text = segment.get("simpleText") or text_from(segment.get("text"))
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    text=text,
                    start_ms=parse_timestamp_ms(timestamp),
                    time=timestamp,
                )
            )

    if segments:
        return segments

    for renderer in find_all_keys(data, "transcriptSegmentRenderer"):
        text = text_from(renderer.get("snippet"))
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                text=text,
                start_ms=int_or_none(renderer.get("startMs")),
                end_ms=int_or_none(renderer.get("endMs")),
                duration_ms=duration_from_bounds(renderer.get("startMs"), renderer.get("endMs")),
                time=text_from(renderer.get("startTimeText")),
            )
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
            TranscriptSegment(
                text=text,
                start_ms=int_or_none(cue_renderer.get("startOffsetMs")),
                duration_ms=int_or_none(cue_renderer.get("durationMs")),
                time=text_from(cue_renderer.get("timestamp")),
            )
        )

    return segments


def find_transcript_panel_params(initial: dict[str, Any]) -> list[str]:
    """Find ``get_panel`` params for the transcript engagement panel."""
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


# ---------------------------------------------------------------------------
# Comment parsing
# ---------------------------------------------------------------------------

def find_comment_continuation(payload: dict[str, Any]) -> str | None:
    """Find the continuation token for the comments section."""
    preferred_tokens: list[str] = []
    fallback_tokens: list[str] = []
    comment_markers = (
        "GNvbW1lbnRzLXNlY3Rpb24",
        "Y29tbWVudHMtc2VjdGlvbg",
        "ZW5nYWdlbWVudC1wYW5lbC1jb21tZW50cy1zZWN0aW9u",
    )
    for key in ("continuationItemRenderer", "reloadContinuationItemsCommand", "appendContinuationItemsAction"):
        for node in find_all_keys(payload, key):
            token = _token_from_node(node)
            if token:
                if any(marker in token for marker in comment_markers):
                    preferred_tokens.append(token)
                else:
                    fallback_tokens.append(token)
    return (preferred_tokens or fallback_tokens or [None])[0]


def _token_from_node(node: Any) -> str | None:
    """Recursively extract a continuation token from a node tree."""
    if isinstance(node, dict):
        endpoint = node.get("continuationEndpoint") or node.get("button", {}).get("buttonRenderer", {}).get("command")
        if endpoint:
            token = endpoint.get("continuationCommand", {}).get("token")
            if token:
                return token
        for value in node.values():
            token = _token_from_node(value)
            if token:
                return token
    elif isinstance(node, list):
        for item in node:
            token = _token_from_node(item)
            if token:
                return token
    return None


def find_comment_count(payload: dict[str, Any]) -> int | None:
    """Find the total comment count from a payload."""
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


def parse_comment(renderer: dict[str, Any]) -> Comment:
    """Parse a legacy ``commentRenderer`` into a :class:`Comment`."""
    author_endpoint = renderer.get("authorEndpoint", {}).get("browseEndpoint", {})
    return Comment(
        comment_id=renderer.get("commentId"),
        author=text_from(renderer.get("authorText")),
        author_channel_id=author_endpoint.get("browseId"),
        text=text_from(renderer.get("contentText")),
        published=text_from(renderer.get("publishedTimeText")),
        likes=parse_compact_number(text_from(renderer.get("voteCount"))) or 0,
        reply_count=int_or_none(text_from(renderer.get("replyCount"))) or 0,
        is_pinned=bool(renderer.get("pinnedCommentBadge")),
        is_hearted=bool(renderer.get("creatorHeart")),
    )


def parse_comment_entity(entity: dict[str, Any]) -> Comment:
    """Parse a modern ``commentEntityPayload`` into a :class:`Comment`."""
    properties = entity.get("properties", {})
    author = entity.get("author", {})
    toolbar = entity.get("toolbar", {})
    content = properties.get("content", {})
    author_endpoint = author.get("channelCommand", {}).get("innertubeCommand", {}).get("browseEndpoint", {})

    return Comment(
        comment_id=properties.get("commentId"),
        author=author.get("displayName") or properties.get("authorButtonA11y"),
        author_channel_id=author.get("channelId") or author_endpoint.get("browseId"),
        author_channel_url=author_endpoint.get("canonicalBaseUrl"),
        text=content.get("content") if isinstance(content, dict) else None,
        published=properties.get("publishedTime"),
        likes=parse_compact_number(toolbar.get("likeCountA11y"))
        or parse_compact_number(toolbar.get("likeCountNotliked"))
        or 0,
        reply_count=parse_compact_number(toolbar.get("replyCountA11y"))
        or parse_compact_number(toolbar.get("replyCount"))
        or 0,
        is_pinned=bool(entity.get("pinned")),
        is_hearted="heartActiveTooltip" in toolbar,
    )
