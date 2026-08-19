"""Tests for sentiment analysis functions."""

from __future__ import annotations

import pytest

from media_data_extractor.core.models import (
    AccessStatus,
    Comment,
    Engagement,
    NetworkInfo,
    Summary,
    Transcript,
    VideoMetadata,
    VideoResult,
)
from media_data_extractor.analytics.sentiment import (
    CommentSentiment,
    SentimentResult,
    VideoSentiment,
    analyze_comment_sentiment,
    analyze_sentiment,
    analyze_video_sentiment,
)


class TestAnalyzeSentiment:
    def test_empty_text(self):
        result = analyze_sentiment("")
        assert result.compound == 0.0
        assert result.label == "neutral"

    def test_positive_text(self):
        result = analyze_sentiment("This is a great and amazing video, I love it!")
        assert result.compound > 0.05
        assert result.label == "positive"

    def test_negative_text(self):
        result = analyze_sentiment("This is terrible and awful, I hate it.")
        assert result.compound < -0.05
        assert result.label == "negative"

    def test_neutral_text(self):
        result = analyze_sentiment("The video is about Python programming.")
        assert result.label == "neutral"

    def test_negation(self):
        result = analyze_sentiment("This is not good")
        # "not good" should be less positive than "good"
        positive = analyze_sentiment("This is good")
        assert result.compound < positive.compound

    def test_booster(self):
        result = analyze_sentiment("This is very good")
        positive = analyze_sentiment("This is good")
        assert result.compound > positive.compound

    def test_compound_in_range(self):
        result = analyze_sentiment("Amazing wonderful incredible best!")
        assert -1.0 <= result.compound <= 1.0

    def test_word_count(self):
        result = analyze_sentiment("This is a test sentence with words")
        assert result.word_count > 0

    def test_to_dict(self):
        result = analyze_sentiment("Great video!")
        d = result.to_dict()
        assert "compound" in d
        assert "label" in d
        assert "positive" in d
        assert "negative" in d
        assert "neutral" in d

    def test_exclamation_amplifies(self):
        with_exclaim = analyze_sentiment("Great!")
        without = analyze_sentiment("Great")
        assert with_exclaim.compound >= without.compound


class TestAnalyzeCommentSentiment:
    def _make_comment(self, text: str = "Great video!") -> Comment:
        return Comment(
            comment_id="c1",
            likes=5,
            reply_count=0,
            is_pinned=False,
            is_hearted=False,
            author="Alice",
            text=text,
        )

    def test_basic(self):
        comment = self._make_comment("This is amazing!")
        result = analyze_comment_sentiment(comment)
        assert isinstance(result, CommentSentiment)
        assert result.sentiment.label == "positive"

    def test_negative_comment(self):
        comment = self._make_comment("This is terrible and boring")
        result = analyze_comment_sentiment(comment)
        assert result.sentiment.label == "negative"

    def test_to_dict(self):
        comment = self._make_comment("Great!")
        result = analyze_comment_sentiment(comment)
        d = result.to_dict()
        assert "sentiment" in d


class TestAnalyzeVideoSentiment:
    def _make_video(self, comments: list[Comment] | None = None) -> VideoResult:
        if comments is None:
            comments = [
                Comment(comment_id="c1", likes=5, reply_count=0, is_pinned=False, is_hearted=False, author="A", text="Great!"),
                Comment(comment_id="c2", likes=2, reply_count=0, is_pinned=False, is_hearted=False, author="B", text="Terrible"),
                Comment(comment_id="c3", likes=1, reply_count=0, is_pinned=False, is_hearted=False, author="C", text="Okay"),
            ]
        return VideoResult(
            video_id="vid1",
            source_url="https://www.youtube.com/watch?v=vid1",
            metadata=VideoMetadata(video_url="https://www.youtube.com/watch?v=vid1"),
            engagement=Engagement(comment_count_scraped=len(comments)),
            transcript=Transcript(available=False),
            summary=Summary(available=False, text=""),
            comments=comments,
            network=NetworkInfo(access_status=AccessStatus(blocked=False)),
        )

    def test_basic(self):
        video = self._make_video()
        result = analyze_video_sentiment(video)
        assert isinstance(result, VideoSentiment)
        assert result.total_comments == 3
        assert result.positive_count >= 1
        assert result.negative_count >= 1

    def test_no_comments(self):
        video = self._make_video(comments=[])
        result = analyze_video_sentiment(video)
        assert result.total_comments == 0
        assert result.average_compound == 0.0
        assert result.overall_label == "neutral"

    def test_to_dict(self):
        video = self._make_video()
        result = analyze_video_sentiment(video)
        d = result.to_dict()
        assert d["total_comments"] == 3
        assert "comment_sentiments" in d
        assert len(d["comment_sentiments"]) == 3

    def test_all_positive(self):
        comments = [
            Comment(comment_id=f"c{i}", likes=1, reply_count=0, is_pinned=False, is_hearted=False, author="A", text="Amazing!")
            for i in range(5)
        ]
        video = self._make_video(comments=comments)
        result = analyze_video_sentiment(video)
        assert result.overall_label == "positive"
        assert result.positive_count == 5

    def test_all_negative(self):
        comments = [
            Comment(comment_id=f"c{i}", likes=1, reply_count=0, is_pinned=False, is_hearted=False, author="A", text="Terrible and awful")
            for i in range(5)
        ]
        video = self._make_video(comments=comments)
        result = analyze_video_sentiment(video)
        assert result.overall_label == "negative"
        assert result.negative_count == 5
