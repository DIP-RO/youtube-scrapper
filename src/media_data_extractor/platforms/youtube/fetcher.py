"""Network-level fetching functions for transcripts, comments, and dislikes.

These functions make HTTP requests to YouTube's innertube API and the
Return YouTube Dislike API.  They are kept separate from the
:class:`~media_data_extractor.client.YouTubeScraper` orchestration class
so they can be tested in isolation with mocked HTTP sessions.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import requests

from ...core.models import Comment, DislikeData, Transcript, TranscriptSegment
from .parser import (
    choose_caption_track,
    find_comment_continuation,
    find_comment_count,
    find_transcript_panel_params,
    parse_comment,
    parse_comment_entity,
    parse_panel_transcript_segments,
)
from ...utils.helpers import find_all_keys, int_or_none, text_from

logger = logging.getLogger(__name__)

YOUTUBEI_BASE = "https://www.youtube.com/youtubei/v1"
RYD_API = "https://returnyoutubedislikeapi.com/votes"


# ---------------------------------------------------------------------------
# Dislikes (Return YouTube Dislike API)
# ---------------------------------------------------------------------------

def fetch_dislikes(session: requests.Session, video_id: str) -> DislikeData | None:
    """Fetch dislike data from the third-party Return YouTube Dislike API.

    Returns ``None`` if the API is unavailable or the video is not found.
    """
    try:
        response = session.get(RYD_API, params={"videoId": video_id}, timeout=12)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.debug("Return YouTube Dislike API failed for %s: %s", video_id, exc)
        return None

    return DislikeData(
        source="returnyoutubedislikeapi.com",
        dislikes=data.get("dislikes"),
        likes=data.get("likes"),
        rating=data.get("rating"),
        view_count=data.get("viewCount"),
    )


# ---------------------------------------------------------------------------
# Transcripts
# ---------------------------------------------------------------------------

def fetch_transcript(
    session: requests.Session,
    player: dict[str, Any],
    preferred_lang: str,
    *,
    initial: dict[str, Any] | None = None,
    api_key: str | None = None,
    context: dict[str, Any] | None = None,
) -> Transcript:
    """Fetch a transcript for a video.

    Tries the timedtext caption URL first, then falls back to the
    ``get_panel`` innertube endpoint.
    """
    tracks = (
        player.get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks", [])
    )
    if not tracks:
        panel = fetch_panel_transcript(session, initial or {}, api_key=api_key, context=context)
        return panel

    track = choose_caption_track(tracks, preferred_lang)
    base_url = track.get("baseUrl")
    if not base_url:
        panel = fetch_panel_transcript(session, initial or {}, api_key=api_key, context=context)
        return panel

    separator = "&" if "?" in base_url else "?"
    url = f"{base_url}{separator}fmt=json3"
    caption_error: str | None = None
    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.debug("Timedtext fetch failed: %s", exc)
        data = {}
        caption_error = "caption_track_unavailable"

    segments: list[TranscriptSegment] = []
    for event in data.get("events", []):
        pieces = event.get("segs") or []
        text = "".join(piece.get("utf8", "") for piece in pieces).strip()
        if text:
            segments.append(
                TranscriptSegment(
                    text=text,
                    start_ms=event.get("tStartMs"),
                    duration_ms=event.get("dDurationMs"),
                )
            )

    if segments:
        return Transcript(
            available=True,
            segments=segments,
            text=" ".join(seg.text for seg in segments),
            language=track.get("languageCode"),
            name=text_from(track.get("name")),
            is_auto_generated=track.get("kind") == "asr",
            source="timedtext",
        )

    panel = fetch_panel_transcript(session, initial or {}, api_key=api_key, context=context)
    if panel.available:
        if not panel.language:
            panel.language = track.get("languageCode")
        if not panel.name:
            panel.name = text_from(track.get("name"))
        if panel.is_auto_generated is None:
            panel.is_auto_generated = track.get("kind") == "asr"
        return panel

    return Transcript(
        available=False,
        language=track.get("languageCode"),
        name=text_from(track.get("name")),
        is_auto_generated=track.get("kind") == "asr",
        error=caption_error or "no_transcript_segments",
    )


def fetch_panel_transcript(
    session: requests.Session,
    initial: dict[str, Any],
    *,
    api_key: str | None,
    context: dict[str, Any] | None,
) -> Transcript:
    """Fetch a transcript via the ``youtubei/v1/get_panel`` endpoint."""
    if not api_key or not context:
        return Transcript(available=False)

    for panel_params in find_transcript_panel_params(initial):
        endpoint = f"{YOUTUBEI_BASE}/get_panel?prettyPrint=false&key={quote(api_key)}"
        try:
            response = session.post(endpoint, json={"context": context, "params": panel_params}, timeout=20)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.debug("get_panel transcript fetch failed: %s", exc)
            continue

        segments = parse_panel_transcript_segments(data)
        if segments:
            return Transcript(
                available=True,
                segments=segments,
                text=" ".join(seg.text for seg in segments),
                source="youtubei_get_panel",
            )

    return Transcript(available=False)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def fetch_comment_data(
    session: requests.Session,
    initial: dict[str, Any],
    *,
    api_key: str | None,
    context: dict[str, Any],
    max_comments: int,
) -> tuple[int | None, list[Comment]]:
    """Fetch up to *max_comments* comments via the innertube ``next`` endpoint.

    Returns ``(comment_count, comments)`` where ``comment_count`` is the
    total count reported by YouTube (may be ``None``).
    """
    if max_comments <= 0 or not api_key:
        return find_comment_count(initial), []

    continuation = find_comment_continuation(initial)
    comments: list[Comment] = []
    seen: set[str] = set()
    comment_count = find_comment_count(initial)

    while continuation and len(comments) < max_comments:
        endpoint = f"{YOUTUBEI_BASE}/next?key={quote(api_key)}"
        payload = {"context": context, "continuation": continuation}
        try:
            response = session.post(endpoint, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.debug("Comment continuation fetch failed: %s", exc)
            break

        comment_count = find_comment_count(data) or comment_count

        for renderer in find_all_keys(data, "commentRenderer"):
            comment_id = renderer.get("commentId")
            if comment_id and comment_id in seen:
                continue
            dedup_key = comment_id or str(renderer)[:80]
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            comments.append(parse_comment(renderer))
            if len(comments) >= max_comments:
                break

        for entity in find_all_keys(data, "commentEntityPayload"):
            comment = parse_comment_entity(entity)
            comment_id = comment.comment_id
            if not comment_id or comment_id in seen:
                continue
            seen.add(comment_id)
            comments.append(comment)
            if len(comments) >= max_comments:
                break

        continuation = find_comment_continuation(data)

    return comment_count, comments
