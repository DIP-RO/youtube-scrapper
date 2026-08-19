"""Tests for pure utility functions in media_data_extractor.utils.helpers."""

from __future__ import annotations

import pytest

from media_data_extractor.utils.helpers import (
    detect_access_block,
    duration_from_bounds,
    extract_video_id,
    find_all_keys,
    find_key,
    int_or_none,
    parse_compact_number,
    parse_timestamp_ms,
    split_sentences,
    summarize_text,
    text_from,
)


# ---------------------------------------------------------------------------
# extract_video_id
# ---------------------------------------------------------------------------

class TestExtractVideoId:
    def test_watch_url(self):
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_youtu_be_url(self):
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_bare_id(self):
        assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_watch_url_with_extra_params(self):
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s&feature=share") == "dQw4w9WgXcQ"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Could not extract"):
            extract_video_id("https://example.com/page")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            extract_video_id("")

    def test_too_short_id_raises(self):
        with pytest.raises(ValueError):
            extract_video_id("abc")


# ---------------------------------------------------------------------------
# parse_compact_number
# ---------------------------------------------------------------------------

class TestParseCompactNumber:
    def test_thousands(self):
        assert parse_compact_number("1.2K") == 1200

    def test_millions(self):
        assert parse_compact_number("3.4M subscribers") == 3_400_000

    def test_billions(self):
        assert parse_compact_number("5.5B views") == 5_500_000_000

    def test_plain_number(self):
        assert parse_compact_number("987 views") == 987

    def test_with_commas(self):
        assert parse_compact_number("1,234,567") == 1_234_567

    def test_none_input(self):
        assert parse_compact_number(None) is None

    def test_empty_string(self):
        assert parse_compact_number("") is None

    def test_no_number(self):
        assert parse_compact_number("no digits here!") is None


# ---------------------------------------------------------------------------
# int_or_none
# ---------------------------------------------------------------------------

class TestIntOrNone:
    def test_int_input(self):
        assert int_or_none(42) == 42

    def test_string_with_compact(self):
        assert int_or_none("1.5K") == 1500

    def test_string_with_non_digits(self):
        assert int_or_none("1,234 views") == 1234

    def test_none(self):
        assert int_or_none(None) is None

    def test_empty_string(self):
        assert int_or_none("") is None


# ---------------------------------------------------------------------------
# parse_timestamp_ms
# ---------------------------------------------------------------------------

class TestParseTimestampMs:
    def test_minutes_seconds(self):
        assert parse_timestamp_ms("8:43") == 523000

    def test_hours_minutes_seconds(self):
        assert parse_timestamp_ms("1:02:03") == 3_723_000

    def test_none(self):
        assert parse_timestamp_ms(None) is None

    def test_empty(self):
        assert parse_timestamp_ms("") is None

    def test_non_numeric(self):
        assert parse_timestamp_ms("ab:cd") is None


# ---------------------------------------------------------------------------
# duration_from_bounds
# ---------------------------------------------------------------------------

class TestDurationFromBounds:
    def test_valid_bounds(self):
        assert duration_from_bounds(1000, 5000) == 4000

    def test_string_bounds(self):
        assert duration_from_bounds("1000", "5000") == 4000

    def test_none_start(self):
        assert duration_from_bounds(None, 5000) is None

    def test_none_end(self):
        assert duration_from_bounds(1000, None) is None


# ---------------------------------------------------------------------------
# text_from
# ---------------------------------------------------------------------------

class TestTextFrom:
    def test_plain_string(self):
        assert text_from("Hello") == "Hello"

    def test_html_escaped_string(self):
        assert text_from("Hello &amp; goodbye") == "Hello & goodbye"

    def test_simple_text_dict(self):
        assert text_from({"simpleText": "Hi there"}) == "Hi there"

    def test_runs_dict(self):
        assert text_from({"runs": [{"text": "Hello "}, {"text": "world"}]}) == "Hello world"

    def test_accessibility_label(self):
        assert text_from({"accessibility": {"accessibilityData": {"label": "5 likes"}}}) == "5 likes"

    def test_none(self):
        assert text_from(None) is None

    def test_empty_dict(self):
        assert text_from({}) is None


# ---------------------------------------------------------------------------
# find_key / find_all_keys
# ---------------------------------------------------------------------------

class TestFindKey:
    def test_top_level(self):
        data = {"a": 1, "b": 2}
        assert find_key(data, "a") == 1

    def test_nested(self):
        data = {"a": {"b": {"c": 42}}}
        assert find_key(data, "c") == 42

    def test_in_list(self):
        data = {"items": [{"x": 1}, {"y": 2}, {"x": 3}]}
        assert find_key(data, "y") == 2

    def test_not_found(self):
        assert find_key({"a": 1}, "z") is None


class TestFindAllKeys:
    def test_multiple_matches(self):
        data = {"a": [{"x": 1}, {"x": 2}], "x": 3}
        # find_all_keys checks the top-level key first, then recurses into values
        result = find_all_keys(data, "x")
        assert set(result) == {1, 2, 3}
        assert len(result) == 3

    def test_no_matches(self):
        assert find_all_keys({"a": 1}, "z") == []


# ---------------------------------------------------------------------------
# detect_access_block
# ---------------------------------------------------------------------------

class TestDetectAccessBlock:
    def test_unusual_traffic(self):
        result = detect_access_block("<html>our systems have detected unusual traffic</html>")
        assert result["blocked"] is True
        assert "unusual_traffic" in result["reasons"]

    def test_captcha(self):
        result = detect_access_block("<html>recaptcha/api2 challenge</html>")
        assert result["blocked"] is True
        assert "captcha" in result["reasons"]

    def test_consent(self):
        result = detect_access_block("<html>before you continue to youtube consent.youtube.com</html>")
        assert result["blocked"] is True
        assert "consent" in result["reasons"]

    def test_sign_in_required(self):
        result = detect_access_block("<html>sign in to confirm you are not a bot</html>")
        assert result["blocked"] is True
        assert "sign_in_required" in result["reasons"]

    def test_normal_page(self):
        result = detect_access_block("<script>var ytInitialPlayerResponse = {}</script>")
        assert result["blocked"] is False
        assert result["reasons"] == []

    def test_normal_page_with_recaptcha_asset(self):
        result = detect_access_block(
            "<script>var ytInitialPlayerResponse = {}</script><script src='recaptcha/api2'></script>"
        )
        assert result["blocked"] is False

    def test_player_missing(self):
        result = detect_access_block("<html>some random page without player</html>")
        assert result["blocked"] is True
        assert "player_missing" in result["reasons"]


# ---------------------------------------------------------------------------
# summarize_text
# ---------------------------------------------------------------------------

class TestSummarizeText:
    def test_empty_text(self):
        result = summarize_text("")
        assert result["available"] is False
        assert result["method"] == "none"

    def test_short_text_passthrough(self):
        text = "This is one useful sentence about the video. This is another useful sentence."
        result = summarize_text(text)
        assert result["available"] is True
        assert result["method"] == "short_text_passthrough"
        assert "useful sentence" in result["text"]

    def test_frequency_extractive(self):
        sentences = [f"The algorithm processes data efficiently. " for _ in range(10)]
        text = " ".join(sentences)
        result = summarize_text(text, max_sentences=3)
        assert result["available"] is True
        assert result["method"] == "frequency_extractive"

    def test_lead_sentences_fallback(self):
        text = "12345 67890 12345 67890. " * 10
        result = summarize_text(text, max_sentences=2)
        assert result["available"] is True


class TestSplitSentences:
    def test_basic_split(self):
        text = "First sentence is long enough. Second sentence here!"
        result = split_sentences(text)
        assert len(result) == 2

    def test_short_sentences_filtered(self):
        text = "Hi. Hello there everyone, how are you doing?"
        result = split_sentences(text)
        assert all(len(s) > 20 for s in result)
