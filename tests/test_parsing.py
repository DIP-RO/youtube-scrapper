"""Tests for YouTube payload parsing functions in media_data_extractor.platforms.youtube.parser."""

from __future__ import annotations

import pytest

from media_data_extractor.platforms.youtube.parser import (
    choose_caption_track,
    extract_api_key,
    extract_innertube_context,
    extract_json_assignment,
    extract_ytcfg,
    find_comment_continuation,
    find_comment_count,
    find_like_count,
    find_transcript_panel_params,
    parse_comment,
    parse_comment_entity,
    parse_metadata,
    parse_panel_transcript_segments,
)


# ---------------------------------------------------------------------------
# extract_json_assignment
# ---------------------------------------------------------------------------

class TestExtractJsonAssignment:
    def test_var_assignment(self):
        html = '<script>var ytInitialPlayerResponse = {"playabilityStatus":{"status":"OK"}};</script>'
        result = extract_json_assignment(html, "ytInitialPlayerResponse")
        assert result is not None
        assert result["playabilityStatus"]["status"] == "OK"

    def test_window_assignment(self):
        html = '<script>window["ytInitialData"] = {"contents":{}};</script>'
        result = extract_json_assignment(html, "ytInitialData")
        assert result is not None
        assert "contents" in result

    def test_not_found(self):
        assert extract_json_assignment("<html>no json here</html>", "ytInitialPlayerResponse") is None

    def test_nested_braces(self):
        html = 'var x = {"a": {"b": {"c": 1}}, "d": 2};'
        result = extract_json_assignment(html, "x")
        assert result is not None
        assert result["a"]["b"]["c"] == 1
        assert result["d"] == 2

    def test_string_with_braces(self):
        html = 'var x = {"text": "this has {braces} inside"};'
        result = extract_json_assignment(html, "x")
        assert result is not None
        assert result["text"] == "this has {braces} inside"


# ---------------------------------------------------------------------------
# extract_ytcfg
# ---------------------------------------------------------------------------

class TestExtractYtcfg:
    def test_with_innertube_context(self):
        html = 'ytcfg.set({"INNERTUBE_CONTEXT":{"client":{"clientName":"WEB"}}});'
        result = extract_ytcfg(html)
        assert result is not None
        assert "INNERTUBE_CONTEXT" in result
        assert result["INNERTUBE_CONTEXT"]["client"]["clientName"] == "WEB"

    def test_without_innertube_context(self):
        html = 'ytcfg.set({"someOtherKey": 123});'
        assert extract_ytcfg(html) is None

    def test_multiple_ytcfg_sets(self):
        html = (
            'ytcfg.set({"foo": 1});'
            'ytcfg.set({"INNERTUBE_CONTEXT":{"client":{"clientName":"WEB"}}});'
        )
        result = extract_ytcfg(html)
        assert result is not None
        assert "INNERTUBE_CONTEXT" in result


# ---------------------------------------------------------------------------
# extract_api_key
# ---------------------------------------------------------------------------

class TestExtractApiKey:
    def test_from_html(self):
        html = '"INNERTUBE_API_KEY":"AIzaSyTestKey123456789"'
        assert extract_api_key(html, []) == "AIzaSyTestKey123456789"

    def test_from_url_in_events(self):
        events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {"request": {"url": "https://www.youtube.com/youtubei/v1/next?key=AIzaSyFromEvent"}},
            }
        ]
        assert extract_api_key("", events) == "AIzaSyFromEvent"

    def test_not_found(self):
        assert extract_api_key("no key here", []) is None


# ---------------------------------------------------------------------------
# extract_innertube_context
# ---------------------------------------------------------------------------

class TestExtractInnertubeContext:
    def test_from_html(self):
        html = '"INNERTUBE_CONTEXT":{"client":{"clientName":"WEB","clientVersion":"2.0"}},"INNERTUBE_CONTEXT_CLIENT_NAME"'
        ctx = extract_innertube_context(html)
        assert ctx["client"]["clientName"] == "WEB"

    def test_fallback(self):
        html = "no context here"
        ctx = extract_innertube_context(html)
        assert ctx["client"]["clientName"] == "WEB"
        assert ctx["client"]["clientVersion"] == "2.20240601.00.00"


# ---------------------------------------------------------------------------
# parse_metadata
# ---------------------------------------------------------------------------

class TestParseMetadata:
    def test_full_metadata(self):
        player = {
            "videoDetails": {
                "title": "Test Video",
                "shortDescription": "A test description",
                "viewCount": "12345",
                "author": "Test Channel",
                "channelId": "UC123",
                "lengthSeconds": "300",
                "isLiveContent": False,
                "keywords": ["test", "video"],
                "thumbnail": {"thumbnails": [{"url": "https://example.com/thumb.jpg"}]},
            },
            "microformat": {
                "playerMicroformatRenderer": {
                    "uploadDate": "2024-01-01",
                    "publishDate": "2024-01-02",
                    "category": "Education",
                    "ownerProfileUrl": "https://www.youtube.com/channel/UC123",
                }
            },
        }
        initial = {
            "contents": {
                "videoOwnerRenderer": {
                    "title": {"simpleText": "Test Channel"},
                    "subscriberCountText": {"simpleText": "1.5M subscribers"},
                }
            }
        }

        meta = parse_metadata("dQw4w9WgXcQ", player, initial)
        assert meta["title"] == "Test Video"
        assert meta["description"] == "A test description"
        assert meta["views"] == 12345
        assert meta["channel_name"] == "Test Channel"
        assert meta["channel_id"] == "UC123"
        assert meta["channel_url"] == "https://www.youtube.com/channel/UC123"
        assert meta["channel_subscribers"] == "1.5M subscribers"
        assert meta["upload_date"] == "2024-01-01"
        assert meta["duration_seconds"] == 300
        assert meta["category"] == "Education"
        assert meta["keywords"] == ["test", "video"]
        assert meta["thumbnail"] == "https://example.com/thumb.jpg"
        assert meta["video_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_channel_url_fallback(self):
        player = {
            "videoDetails": {
                "channelId": "UC456",
            },
        }
        meta = parse_metadata("abc123", player, {})
        assert meta["channel_url"] == "https://www.youtube.com/channel/UC456"

    def test_empty_payloads(self):
        meta = parse_metadata("abc123", {}, {})
        assert meta["title"] is None
        assert meta["views"] is None
        assert meta["keywords"] == []


# ---------------------------------------------------------------------------
# find_like_count
# ---------------------------------------------------------------------------

class TestFindLikeCount:
    def test_from_segmented_button(self):
        initial = {
            "segmentedLikeDislikeButtonViewModel": {
                "likeButton": {"viewModel": {"content": "1.2K"}},
            }
        }
        assert find_like_count(initial) == 1200

    def test_not_found(self):
        assert find_like_count({}) is None


# ---------------------------------------------------------------------------
# choose_caption_track
# ---------------------------------------------------------------------------

class TestChooseCaptionTrack:
    def test_preferred_non_asr(self):
        tracks = [
            {"languageCode": "en", "kind": "asr"},
            {"languageCode": "en", "name": {"simpleText": "English"}},
        ]
        track = choose_caption_track(tracks, "en")
        assert track["name"]["simpleText"] == "English"

    def test_preferred_any(self):
        tracks = [{"languageCode": "en", "kind": "asr"}]
        track = choose_caption_track(tracks, "en")
        assert track["languageCode"] == "en"

    def test_vss_id_fallback(self):
        tracks = [{"languageCode": "unknown", "vssId": ".en"}]
        track = choose_caption_track(tracks, "en")
        assert track["vssId"] == ".en"

    def test_first_track_fallback(self):
        tracks = [{"languageCode": "fr"}, {"languageCode": "de"}]
        track = choose_caption_track(tracks, "en")
        assert track["languageCode"] == "fr"


# ---------------------------------------------------------------------------
# parse_panel_transcript_segments
# ---------------------------------------------------------------------------

class TestParsePanelTranscriptSegments:
    def test_macro_markers_format(self):
        payload = {
            "macroMarkersPanelItemViewModel": {
                "item": {
                    "timelineItemViewModel": {
                        "timestamp": "8:43",
                        "contentItems": [
                            {
                                "transcriptSegmentViewModel": {
                                    "simpleText": "Important text here"
                                }
                            }
                        ],
                    }
                }
            }
        }
        segments = parse_panel_transcript_segments(payload)
        assert len(segments) == 1
        assert segments[0].text == "Important text here"
        assert segments[0].start_ms == 523000
        assert segments[0].time == "8:43"

    def test_transcript_segment_renderer_format(self):
        payload = {
            "transcriptSegmentRenderer": {
                "snippet": {"runs": [{"text": "Segment text"}]},
                "startMs": "1000",
                "endMs": "3000",
                "startTimeText": {"simpleText": "0:01"},
            }
        }
        segments = parse_panel_transcript_segments(payload)
        assert len(segments) == 1
        assert segments[0].text == "Segment text"
        assert segments[0].start_ms == 1000
        assert segments[0].end_ms == 3000
        assert segments[0].duration_ms == 2000

    def test_cue_group_format(self):
        payload = {
            "transcriptCueGroupRenderer": {
                "cue": {
                    "transcriptCueRenderer": {
                        "cue": {"runs": [{"text": "Cue text"}]},
                        "startOffsetMs": "500",
                        "durationMs": "2000",
                        "timestamp": {"simpleText": "0:00"},
                    }
                }
            }
        }
        segments = parse_panel_transcript_segments(payload)
        assert len(segments) == 1
        assert segments[0].text == "Cue text"
        assert segments[0].start_ms == 500
        assert segments[0].duration_ms == 2000

    def test_no_segments(self):
        assert parse_panel_transcript_segments({}) == []


# ---------------------------------------------------------------------------
# find_transcript_panel_params
# ---------------------------------------------------------------------------

class TestFindTranscriptPanelParams:
    def test_from_engagement_panel(self):
        initial = {
            "showEngagementPanelEndpoint": {
                "identifier": {"tag": "PAmodern_transcript_view"},
                "globalConfiguration": {"params": "abc123param"},
            }
        }
        assert find_transcript_panel_params(initial) == ["abc123param"]

    def test_from_update_command(self):
        initial = {
            "updateEngagementPanelContentCommand": {
                "contentSourcePanelIdentifier": {"tag": "PAmodern_transcript_view"},
                "globalConfiguration": {"params": "xyz789"},
            }
        }
        assert find_transcript_panel_params(initial) == ["xyz789"]

    def test_deduplication(self):
        initial = {
            "showEngagementPanelEndpoint": {
                "identifier": {"tag": "PAmodern_transcript_view"},
                "globalConfiguration": {"params": "same"},
            },
            "updateEngagementPanelContentCommand": {
                "contentSourcePanelIdentifier": {"tag": "PAmodern_transcript_view"},
                "globalConfiguration": {"params": "same"},
            },
        }
        assert find_transcript_panel_params(initial) == ["same"]

    def test_none_found(self):
        assert find_transcript_panel_params({}) == []


# ---------------------------------------------------------------------------
# Comment parsing
# ---------------------------------------------------------------------------

class TestFindCommentCount:
    def test_from_header(self):
        payload = {
            "commentsHeaderRenderer": {
                "countText": {"runs": [{"text": "173"}, {"text": " Comments"}]},
            }
        }
        assert find_comment_count(payload) == 173

    def test_from_entry_point_header(self):
        payload = {
            "commentsEntryPointHeaderRenderer": {
                "countText": {"simpleText": "42 comments"},
            }
        }
        assert find_comment_count(payload) == 42

    def test_not_found(self):
        assert find_comment_count({}) is None


class TestFindCommentContinuation:
    def test_preferred_token(self):
        payload = {
            "continuationItemRenderer": {
                "continuationEndpoint": {
                    "continuationCommand": {"token": "Y29tbWVudHMtc2VjdGlvbg123456"}
                }
            }
        }
        token = find_comment_continuation(payload)
        assert token == "Y29tbWVudHMtc2VjdGlvbg123456"

    def test_fallback_token(self):
        payload = {
            "continuationItemRenderer": {
                "continuationEndpoint": {
                    "continuationCommand": {"token": "someothertoken123"}
                }
            }
        }
        token = find_comment_continuation(payload)
        assert token == "someothertoken123"

    def test_none(self):
        assert find_comment_continuation({}) is None


class TestParseComment:
    def test_legacy_renderer(self):
        renderer = {
            "commentId": "abc123",
            "authorText": {"simpleText": "@user1"},
            "authorEndpoint": {"browseEndpoint": {"browseId": "UC123"}},
            "contentText": {"runs": [{"text": "Great video!"}]},
            "publishedTimeText": {"simpleText": "2 days ago"},
            "voteCount": {"simpleText": "1.2K"},
            "replyCount": {"simpleText": "5"},
            "pinnedCommentBadge": {"pinnedCommentBadgeRenderer": {}},
        }
        comment = parse_comment(renderer)
        assert comment.comment_id == "abc123"
        assert comment.author == "@user1"
        assert comment.author_channel_id == "UC123"
        assert comment.text == "Great video!"
        assert comment.published == "2 days ago"
        assert comment.likes == 1200
        assert comment.reply_count == 5
        assert comment.is_pinned is True
        assert comment.is_hearted is False


class TestParseCommentEntity:
    def test_modern_entity(self):
        entity = {
            "properties": {
                "commentId": "xyz789",
                "content": {"content": "Nice discussion"},
                "publishedTime": "3 hours ago",
                "authorButtonA11y": "@fallback",
            },
            "author": {
                "displayName": "@author",
                "channelId": "channel-1",
                "channelCommand": {
                    "innertubeCommand": {
                        "browseEndpoint": {"canonicalBaseUrl": "/@author"},
                    }
                },
            },
            "toolbar": {
                "likeCountA11y": "5 likes",
                "replyCountA11y": "2 replies",
            },
        }
        comment = parse_comment_entity(entity)
        assert comment.comment_id == "xyz789"
        assert comment.author == "@author"
        assert comment.author_channel_id == "channel-1"
        assert comment.author_channel_url == "/@author"
        assert comment.text == "Nice discussion"
        assert comment.published == "3 hours ago"
        assert comment.likes == 5
        assert comment.reply_count == 2
        assert comment.is_pinned is False
        assert comment.is_hearted is False

    def test_hearted(self):
        entity = {
            "properties": {"commentId": "h1"},
            "toolbar": {"heartActiveTooltip": "Hearted"},
        }
        comment = parse_comment_entity(entity)
        assert comment.is_hearted is True
