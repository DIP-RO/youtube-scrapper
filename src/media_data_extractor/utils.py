"""Pure utility functions with no network or browser dependencies.

These helpers handle URL parsing, text extraction, number parsing,
access-block detection, and extractive summarization.  They are
designed to be easily unit-testable in isolation.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from html import unescape
from urllib.parse import parse_qs, urlparse

from typing import Any


# ---------------------------------------------------------------------------
# URL / ID helpers
# ---------------------------------------------------------------------------

def extract_video_id(url_or_id: str) -> str:
    """Extract an 11-character YouTube video ID from a URL or raw ID.

    Supports ``watch?v=``, ``youtu.be/``, ``shorts/``, and bare IDs.

    Raises:
        ValueError: If no valid video ID can be extracted.
    """
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


# ---------------------------------------------------------------------------
# Access-block detection
# ---------------------------------------------------------------------------

def detect_access_block(html: str) -> dict[str, Any]:
    """Inspect watch-page HTML for access challenges.

    Returns a dict with ``blocked``, ``reasons`` (list of reason tags),
    and ``message``.  This function **detects** blocks; it does not
    attempt to bypass them.
    """
    normalized = re.sub(r"\s+", " ", html).lower()
    player_missing = "ytinitialplayerresponse" not in normalized
    captcha_challenge = (
        "our systems have detected unusual traffic" in normalized
        or "to continue, please type the characters" in normalized
        or ("recaptcha/api2" in normalized and player_missing)
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


# ---------------------------------------------------------------------------
# Generic JSON-tree traversal
# ---------------------------------------------------------------------------

def find_key(value: Any, key: str) -> Any:
    """Depth-first search for the first occurrence of *key* in a nested dict/list tree.

    Uses an explicit stack (iterative) to avoid recursion depth limits.
    """
    stack: list[Any] = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if key in current:
                return current[key]
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return None


def find_all_keys(value: Any, key: str) -> list[Any]:
    """Collect **every** value associated with *key* in a nested dict/list tree.

    Uses an explicit stack (iterative) to avoid recursion depth limits on
    deeply nested YouTube payloads.
    """
    results: list[Any] = []
    stack: list[Any] = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if key in current:
                results.append(current[key])
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return results


# ---------------------------------------------------------------------------
# Text / number parsing
# ---------------------------------------------------------------------------

def text_from(value: Any) -> str | None:
    """Extract human-readable text from YouTube's various text representations.

    Handles plain strings, ``{"simpleText": ...}``, ``{"runs": [...]}``,
    and accessibility labels.
    """
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
    """Best-effort conversion of a value to ``int``, returning ``None`` on failure."""
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
    """Parse a compact number string like ``"1.2K"`` or ``"3.4M subscribers"``."""
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


def parse_timestamp_ms(value: str | None) -> int | None:
    """Convert a timestamp like ``"8:43"`` or ``"1:02:03"`` to milliseconds."""
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
    """Compute duration in ms from start/end boundaries."""
    start_ms = int_or_none(start)
    end_ms = int_or_none(end)
    if start_ms is None or end_ms is None:
        return None
    return max(0, end_ms - start_ms)


# ---------------------------------------------------------------------------
# Extractive summarization
# ---------------------------------------------------------------------------

_SUMMARY_STOPWORDS = frozenset({
    "the", "and", "that", "this", "with", "you", "for", "are", "but", "from",
    "have", "not", "your", "was", "will", "they", "their", "about", "there",
    "what", "when", "where", "which", "into", "just", "like", "then", "than",
})


def summarize_text(text: str, max_sentences: int = 5) -> dict[str, Any]:
    """Produce a short extractive summary from *text*.

    Uses a simple word-frequency scoring approach.  Returns a dict with
    ``available``, ``text``, and ``method``.
    """
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return {"available": False, "text": "", "method": "none"}

    sentences = split_sentences(cleaned)
    if len(sentences) <= max_sentences:
        return {"available": True, "text": cleaned, "method": "short_text_passthrough"}

    words = re.findall(r"[A-Za-z][A-Za-z']+", cleaned.lower())
    freqs = Counter(word for word in words if word not in _SUMMARY_STOPWORDS and len(word) > 2)
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
    """Split *text* into sentences longer than 20 characters."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if len(part.strip()) > 20]
