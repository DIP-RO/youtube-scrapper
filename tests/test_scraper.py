"""Tests for network fetching functions in yt_network_scraper.scraper.

All HTTP calls are mocked — no live YouTube requests are made.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from yt_network_scraper.models import Comment, DislikeData, Transcript
from yt_network_scraper.scraper import (
    RYD_API,
    YOUTUBEI_BASE,
    fetch_comment_data,
    fetch_dislikes,
    fetch_panel_transcript,
    fetch_transcript,
)


# ---------------------------------------------------------------------------
# fetch_dislikes
# ---------------------------------------------------------------------------

class TestFetchDislikes:
    def test_success(self):
        session = MagicMock(spec=requests.Session)
        session.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"dislikes": 100, "likes": 500, "rating": 4.5, "viewCount": 10000},
        )
        result = fetch_dislikes(session, "dQw4w9WgXcQ")
        assert result is not None
        assert result.dislikes == 100
        assert result.likes == 500
        assert result.rating == 4.5
        assert result.view_count == 10000
        assert result.source == "returnyoutubedislikeapi.com"

    def test_404_returns_none(self):
        session = MagicMock(spec=requests.Session)
        session.get.return_value = MagicMock(status_code=404)
        assert fetch_dislikes(session, "nonexistent") is None

    def test_network_error_returns_none(self):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.ConnectionError("No connection")
        assert fetch_dislikes(session, "abc123") is None

    def test_json_error_returns_none(self):
        session = MagicMock(spec=requests.Session)
        session.get.return_value = MagicMock(
            status_code=200,
            json=lambda: (_ for _ in ()).throw(ValueError("bad json")),
        )
        assert fetch_dislikes(session, "abc123") is None


# ---------------------------------------------------------------------------
# fetch_transcript
# ---------------------------------------------------------------------------

class TestFetchTranscript:
    def test_no_tracks_returns_unavailable(self):
        session = MagicMock(spec=requests.Session)
        player = {"captions": {}}
        result = fetch_transcript(session, player, "en")
        assert result.available is False

    def test_timedtext_success(self):
        session = MagicMock(spec=requests.Session)
        session.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "events": [
                    {"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "Hello "}]},
                    {"tStartMs": 2000, "dDurationMs": 2000, "segs": [{"utf8": "world"}]},
                ]
            },
        )
        # Note: the scraper strips whitespace from each segment's text
        player = {
            "captions": {
                "playerCaptionsTracklistRenderer": {
                    "captionTracks": [
                        {"languageCode": "en", "baseUrl": "https://example.com/tt", "kind": "asr"}
                    ]
                }
            }
        }
        result = fetch_transcript(session, player, "en")
        assert result.available is True
        assert result.source == "timedtext"
        assert result.language == "en"
        assert result.is_auto_generated is True
        assert len(result.segments) == 2
        assert result.segments[0].text == "Hello"
        assert result.segments[0].start_ms == 0
        assert result.segments[1].text == "world"
        assert result.segments[1].start_ms == 2000
        assert "Hello" in result.text

    def test_timedtext_network_error_falls_back_to_panel(self):
        session = MagicMock(spec=requests.Session)
        # First call (timedtext) fails, second call (panel) also fails
        session.get.side_effect = requests.ConnectionError("fail")
        session.post.return_value = MagicMock(status_code=200, json=lambda: {})
        player = {
            "captions": {
                "playerCaptionsTracklistRenderer": {
                    "captionTracks": [{"languageCode": "en", "baseUrl": "https://example.com/tt"}]
                }
            }
        }
        result = fetch_transcript(session, player, "en", initial={}, api_key="key", context={"client": {}})
        assert result.available is False
        assert result.error == "caption_track_unavailable"

    def test_empty_segments_falls_back_to_panel(self):
        session = MagicMock(spec=requests.Session)
        session.get.return_value = MagicMock(status_code=200, json=lambda: {"events": []})
        session.post.return_value = MagicMock(status_code=200, json=lambda: {})
        player = {
            "captions": {
                "playerCaptionsTracklistRenderer": {
                    "captionTracks": [{"languageCode": "en", "baseUrl": "https://example.com/tt"}]
                }
            }
        }
        result = fetch_transcript(session, player, "en", initial={}, api_key="key", context={"client": {}})
        assert result.available is False
        assert result.error == "no_transcript_segments"


# ---------------------------------------------------------------------------
# fetch_panel_transcript
# ---------------------------------------------------------------------------

class TestFetchPanelTranscript:
    def test_no_api_key_returns_unavailable(self):
        session = MagicMock(spec=requests.Session)
        result = fetch_panel_transcript(session, {}, api_key=None, context={"client": {}})
        assert result.available is False

    def test_no_context_returns_unavailable(self):
        session = MagicMock(spec=requests.Session)
        result = fetch_panel_transcript(session, {}, api_key="key", context=None)
        assert result.available is False

    def test_no_panel_params_returns_unavailable(self):
        session = MagicMock(spec=requests.Session)
        result = fetch_panel_transcript(session, {}, api_key="key", context={"client": {}})
        assert result.available is False

    def test_success_with_segments(self):
        session = MagicMock(spec=requests.Session)
        session.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "macroMarkersPanelItemViewModel": {
                    "item": {
                        "timelineItemViewModel": {
                            "timestamp": "0:05",
                            "contentItems": [
                                {"transcriptSegmentViewModel": {"simpleText": "First segment"}}
                            ],
                        }
                    }
                }
            },
        )
        initial = {
            "showEngagementPanelEndpoint": {
                "identifier": {"tag": "PAmodern_transcript_view"},
                "globalConfiguration": {"params": "testparam"},
            }
        }
        result = fetch_panel_transcript(session, initial, api_key="key", context={"client": {}})
        assert result.available is True
        assert result.source == "youtubei_get_panel"
        assert len(result.segments) == 1
        assert result.segments[0].text == "First segment"

    def test_network_error_continues_to_next_param(self):
        session = MagicMock(spec=requests.Session)
        session.post.side_effect = requests.ConnectionError("fail")
        initial = {
            "showEngagementPanelEndpoint": {
                "identifier": {"tag": "PAmodern_transcript_view"},
                "globalConfiguration": {"params": "param1"},
            }
        }
        result = fetch_panel_transcript(session, initial, api_key="key", context={"client": {}})
        assert result.available is False


# ---------------------------------------------------------------------------
# fetch_comment_data
# ---------------------------------------------------------------------------

class TestFetchCommentData:
    def test_max_comments_zero_returns_empty(self):
        session = MagicMock(spec=requests.Session)
        count, comments = fetch_comment_data(
            session, {}, api_key="key", context={"client": {}}, max_comments=0
        )
        assert comments == []

    def test_no_api_key_returns_empty(self):
        session = MagicMock(spec=requests.Session)
        count, comments = fetch_comment_data(
            session, {}, api_key=None, context={"client": {}}, max_comments=10
        )
        assert comments == []

    def test_no_continuation_returns_empty(self):
        session = MagicMock(spec=requests.Session)
        count, comments = fetch_comment_data(
            session, {}, api_key="key", context={"client": {}}, max_comments=10
        )
        assert comments == []

    def test_fetches_comments(self):
        session = MagicMock(spec=requests.Session)
        initial = {
            "commentsHeaderRenderer": {
                "countText": {"runs": [{"text": "100"}, {"text": " Comments"}]},
            },
            "continuationItemRenderer": {
                "continuationEndpoint": {
                    "continuationCommand": {"token": "Y29tbWVudHMtc2VjdGlvbg_test"}
                }
            },
        }
        # First response has comments, second has none (no continuation)
        session.post.side_effect = [
            MagicMock(
                status_code=200,
                json=lambda: {
                    "commentRenderer": {
                        "commentId": "c1",
                        "authorText": {"simpleText": "@user1"},
                        "contentText": {"runs": [{"text": "Nice!"}]},
                        "publishedTimeText": {"simpleText": "1 day ago"},
                        "voteCount": {"simpleText": "5"},
                        "replyCount": {"simpleText": "0"},
                    },
                    "commentEntityPayload": {
                        "properties": {"commentId": "c2", "content": {"content": "Great!"}},
                        "toolbar": {"likeCountA11y": "3 likes", "replyCountA11y": "1 reply"},
                    },
                },
            ),
        ]
        count, comments = fetch_comment_data(
            session, initial, api_key="key", context={"client": {}}, max_comments=10
        )
        assert count == 100
        assert len(comments) == 2
        assert comments[0].comment_id == "c1"
        assert comments[0].text == "Nice!"
        assert comments[1].comment_id == "c2"
        assert comments[1].text == "Great!"

    def test_respects_max_comments(self):
        session = MagicMock(spec=requests.Session)
        initial = {
            "continuationItemRenderer": {
                "continuationEndpoint": {
                    "continuationCommand": {"token": "Y29tbWVudHMtc2VjdGlvbg_test"}
                }
            },
        }
        session.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "commentRenderer": {
                    "commentId": "c1",
                    "contentText": {"runs": [{"text": "Comment 1"}]},
                    "voteCount": {"simpleText": "1"},
                    "replyCount": {"simpleText": "0"},
                },
            },
        )
        count, comments = fetch_comment_data(
            session, initial, api_key="key", context={"client": {}}, max_comments=1
        )
        assert len(comments) == 1

    def test_network_error_stops_fetching(self):
        session = MagicMock(spec=requests.Session)
        initial = {
            "continuationItemRenderer": {
                "continuationEndpoint": {
                    "continuationCommand": {"token": "Y29tbWVudHMtc2VjdGlvbg_test"}
                }
            },
        }
        session.post.side_effect = requests.ConnectionError("fail")
        count, comments = fetch_comment_data(
            session, initial, api_key="key", context={"client": {}}, max_comments=10
        )
        assert comments == []

    def test_deduplication(self):
        session = MagicMock(spec=requests.Session)
        initial = {
            "continuationItemRenderer": {
                "continuationEndpoint": {
                    "continuationCommand": {"token": "Y29tbWVudHMtc2VjdGlvbg_test"}
                }
            },
        }
        # Both responses contain the same comment ID
        session.post.side_effect = [
            MagicMock(
                status_code=200,
                json=lambda: {
                    "commentRenderer": {
                        "commentId": "dup1",
                        "contentText": {"runs": [{"text": "First"}]},
                        "voteCount": {"simpleText": "1"},
                        "replyCount": {"simpleText": "0"},
                    },
                    "continuationItemRenderer": {
                        "continuationEndpoint": {
                            "continuationCommand": {"token": "Y29tbWVudHMtc2VjdGlvbg_page2"}
                        }
                    },
                },
            ),
            MagicMock(
                status_code=200,
                json=lambda: {
                    "commentRenderer": {
                        "commentId": "dup1",
                        "contentText": {"runs": [{"text": "Duplicate"}]},
                        "voteCount": {"simpleText": "1"},
                        "replyCount": {"simpleText": "0"},
                    },
                },
            ),
        ]
        count, comments = fetch_comment_data(
            session, initial, api_key="key", context={"client": {}}, max_comments=10
        )
        assert len(comments) == 1
        assert comments[0].text == "First"
