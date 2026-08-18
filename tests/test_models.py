"""Tests for data models in media_data_extractor.models."""

from __future__ import annotations

import json

from media_data_extractor.models import (
    AccessStatus,
    Comment,
    DislikeData,
    Engagement,
    NetworkInfo,
    Summary,
    Transcript,
    TranscriptSegment,
    VideoMetadata,
    VideoResult,
)


class TestVideoMetadata:
    def test_defaults(self):
        meta = VideoMetadata(video_url="https://www.youtube.com/watch?v=abc")
        assert meta.title is None
        assert meta.keywords == []
        assert meta.video_url == "https://www.youtube.com/watch?v=abc"

    def test_with_values(self):
        meta = VideoMetadata(
            video_url="https://www.youtube.com/watch?v=abc",
            title="Test Video",
            views=1000,
            keywords=["python", "testing"],
        )
        assert meta.title == "Test Video"
        assert meta.views == 1000
        assert meta.keywords == ["python", "testing"]


class TestTranscriptSegment:
    def test_required_field(self):
        seg = TranscriptSegment(text="Hello world")
        assert seg.text == "Hello world"
        assert seg.start_ms is None
        assert seg.duration_ms is None

    def test_with_timing(self):
        seg = TranscriptSegment(text="Hello", start_ms=1000, duration_ms=2000)
        assert seg.start_ms == 1000
        assert seg.duration_ms == 2000


class TestTranscript:
    def test_unavailable(self):
        t = Transcript(available=False)
        assert t.available is False
        assert t.segments == []
        assert t.text == ""

    def test_with_segments(self):
        seg = TranscriptSegment(text="Hello", start_ms=0)
        t = Transcript(available=True, segments=[seg], text="Hello", language="en")
        assert t.available is True
        assert len(t.segments) == 1
        assert t.language == "en"


class TestComment:
    def test_required_fields(self):
        c = Comment(
            comment_id="abc",
            likes=5,
            reply_count=2,
            is_pinned=False,
            is_hearted=True,
        )
        assert c.comment_id == "abc"
        assert c.likes == 5
        assert c.is_hearted is True


class TestDislikeData:
    def test_with_values(self):
        d = DislikeData(
            source="returnyoutubedislikeapi.com",
            dislikes=100,
            likes=500,
            rating=4.5,
        )
        assert d.dislikes == 100
        assert d.source == "returnyoutubedislikeapi.com"


class TestEngagement:
    def test_defaults(self):
        e = Engagement(comment_count_scraped=0)
        assert e.likes is None
        assert e.dislikes is None

    def test_with_dislike_data(self):
        d = DislikeData(source="ryd", dislikes=10)
        e = Engagement(comment_count_scraped=5, likes=100, dislikes=d)
        assert e.dislikes is not None
        assert e.dislikes.dislikes == 10


class TestVideoResultToDict:
    def test_serialization(self):
        result = VideoResult(
            video_id="dQw4w9WgXcQ",
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            metadata=VideoMetadata(
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title="Test",
                views=100,
            ),
            engagement=Engagement(comment_count_scraped=3, likes=50),
            transcript=Transcript(available=True, text="Hello", segments=[TranscriptSegment(text="Hello")]),
            summary=Summary(available=True, text="Summary", method="short_text_passthrough"),
            comments=[
                Comment(comment_id="c1", likes=1, reply_count=0, is_pinned=False, is_hearted=False),
            ],
            network=NetworkInfo(access_status=AccessStatus(blocked=False)),
        )

        d = result.to_dict()
        assert d["video_id"] == "dQw4w9WgXcQ"
        assert d["metadata"]["title"] == "Test"
        assert d["engagement"]["likes"] == 50
        assert d["transcript"]["available"] is True
        assert len(d["comments"]) == 1
        assert d["comments"][0]["comment_id"] == "c1"
        assert d["network"]["access_status"]["blocked"] is False

        # Must be JSON-serializable
        json.dumps(d)
