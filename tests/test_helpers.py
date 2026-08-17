from yt_network_scraper.scraper import (
    detect_access_block,
    extract_video_id,
    parse_compact_number,
    find_comment_count,
    parse_comment_entity,
    parse_panel_transcript_segments,
    parse_timestamp_ms,
    summarize_text,
)


def test_extract_video_id_from_common_urls():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_parse_compact_number():
    assert parse_compact_number("1.2K") == 1200
    assert parse_compact_number("3.4M subscribers") == 3_400_000
    assert parse_compact_number("987 views") == 987


def test_summary_returns_short_text():
    summary = summarize_text("This is one useful sentence about the video. This is another useful sentence.")
    assert summary["available"] is True
    assert "useful sentence" in summary["text"]


def test_parse_panel_transcript_view_model_segments():
    payload = {
        "content": {
            "macroMarkersPanelItemViewModel": {
                "item": {
                    "timelineItemViewModel": {
                        "timestamp": "8:43",
                        "contentItems": [
                            {
                                "transcriptSegmentViewModel": {
                                    "simpleText": "গুরুত্বপূর্ণ পদে এরকম কথা বলা হয়েছে"
                                }
                            }
                        ],
                    }
                }
            }
        }
    }

    segments = parse_panel_transcript_segments(payload)
    assert segments == [
        {
            "start_ms": 523000,
            "duration_ms": None,
            "time": "8:43",
            "text": "গুরুত্বপূর্ণ পদে এরকম কথা বলা হয়েছে",
        }
    ]


def test_parse_timestamp_ms():
    assert parse_timestamp_ms("8:43") == 523000
    assert parse_timestamp_ms("1:02:03") == 3_723_000


def test_detect_access_block():
    blocked = detect_access_block("<html>our systems have detected unusual traffic recaptcha/api2</html>")
    assert blocked["blocked"] is True
    assert "captcha" in blocked["reasons"]
    assert "unusual_traffic" in blocked["reasons"]

    ok = detect_access_block("<script>var ytInitialPlayerResponse = {}</script>")
    assert ok["blocked"] is False

    normal_with_recaptcha_asset = detect_access_block(
        "<script>var ytInitialPlayerResponse = {}</script><script src='recaptcha/api2'></script>"
    )
    assert normal_with_recaptcha_asset["blocked"] is False


def test_parse_modern_comment_entity_and_count():
    payload = {
        "commentsHeaderRenderer": {
            "countText": {"runs": [{"text": "173"}, {"text": " Comments"}]}
        }
    }
    assert find_comment_count(payload) == 173

    comment = parse_comment_entity(
        {
            "properties": {
                "commentId": "abc",
                "content": {"content": "Nice discussion"},
                "publishedTime": "3 hours ago",
                "authorButtonA11y": "@fallback",
            },
            "author": {
                "channelId": "channel-1",
                "displayName": "@author",
                "channelCommand": {
                    "innertubeCommand": {
                        "browseEndpoint": {"canonicalBaseUrl": "/@author"}
                    }
                },
            },
            "toolbar": {
                "likeCountA11y": "5 likes",
                "replyCountA11y": "2 replies",
            },
        }
    )
    assert comment["comment_id"] == "abc"
    assert comment["author"] == "@author"
    assert comment["likes"] == 5
    assert comment["reply_count"] == 2
