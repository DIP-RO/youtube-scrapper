"""Tests for comment filtering functions."""

from __future__ import annotations

import pytest

from media_data_extractor.filters import CommentFilter, filter_comments, search_comments, top_comments
from media_data_extractor.models import (
    AccessStatus,
    Comment,
    Engagement,
    NetworkInfo,
    Summary,
    Transcript,
    VideoMetadata,
    VideoResult,
)


def _make_video(comments: list[Comment] | None = None) -> VideoResult:
    if comments is None:
        comments = [
            Comment(comment_id="c1", likes=50, reply_count=2, is_pinned=True, is_hearted=False, author="Alice", text="This is a great video about Python"),
            Comment(comment_id="c2", likes=5, reply_count=0, is_pinned=False, is_hearted=False, author="Bob", text="Nice content, very helpful"),
            Comment(comment_id="c3", likes=0, reply_count=0, is_pinned=False, is_hearted=False, author="Charlie", text="I didn't like this at all"),
            Comment(comment_id="c4", likes=100, reply_count=5, is_pinned=False, is_hearted=True, author="Alice2", text="Amazing tutorial!"),
            Comment(comment_id="c5", likes=3, reply_count=0, is_pinned=False, is_hearted=False, author="Dave", text="Thanks for sharing"),
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


class TestCommentFilter:
    def test_keyword_filter(self):
        video = _make_video()
        filtered = filter_comments(video, keyword="great")
        assert len(filtered) == 1
        assert "great" in filtered[0].text.lower()

    def test_author_filter(self):
        video = _make_video()
        filtered = filter_comments(video, author="alice")
        assert len(filtered) == 2  # Alice and Alice2
        assert all("alice" in c.author.lower() for c in filtered)

    def test_min_likes_filter(self):
        video = _make_video()
        filtered = filter_comments(video, min_likes=10)
        assert len(filtered) == 2  # c1 (50) and c4 (100)
        assert all(c.likes >= 10 for c in filtered)

    def test_max_likes_filter(self):
        video = _make_video()
        filtered = filter_comments(video, max_likes=5)
        assert len(filtered) == 3  # c2 (5), c3 (0), c5 (3)
        assert all(c.likes <= 5 for c in filtered)

    def test_likes_range(self):
        video = _make_video()
        filtered = filter_comments(video, min_likes=3, max_likes=50)
        assert len(filtered) == 3  # c1 (50), c2 (5), c5 (3)
        assert all(3 <= c.likes <= 50 for c in filtered)

    def test_regex_filter(self):
        video = _make_video()
        filtered = filter_comments(video, regex=r"Python|tutorial")
        assert len(filtered) == 2
        assert any("python" in c.text.lower() for c in filtered)
        assert any("tutorial" in c.text.lower() for c in filtered)

    def test_sentiment_filter_positive(self):
        video = _make_video()
        filtered = filter_comments(video, sentiment="positive")
        assert all(c.text for c in filtered)
        # "great" and "amazing" comments should be positive
        assert len(filtered) >= 2

    def test_sentiment_filter_negative(self):
        video = _make_video()
        filtered = filter_comments(video, sentiment="negative")
        # "didn't like" should be negative
        assert len(filtered) >= 1

    def test_combined_filters(self):
        video = _make_video()
        filtered = filter_comments(video, keyword="great", min_likes=10)
        assert len(filtered) == 1
        assert filtered[0].comment_id == "c1"

    def test_no_matches(self):
        video = _make_video()
        filtered = filter_comments(video, keyword="nonexistent_keyword_xyz")
        assert len(filtered) == 0

    def test_no_filter_returns_all(self):
        video = _make_video()
        f = CommentFilter()
        filtered = filter_comments(video, filter=f)
        assert len(filtered) == 5

    def test_filter_object(self):
        video = _make_video()
        f = CommentFilter(keyword="amazing", min_likes=50)
        filtered = filter_comments(video, filter=f)
        assert len(filtered) == 1
        assert filtered[0].comment_id == "c4"


class TestSearchComments:
    def test_basic_search(self):
        video = _make_video()
        results = search_comments(video, "python")
        assert len(results) == 1
        assert "python" in results[0].text.lower()

    def test_case_insensitive(self):
        video = _make_video()
        results = search_comments(video, "PYTHON")
        assert len(results) == 1

    def test_no_results(self):
        video = _make_video()
        results = search_comments(video, "xyz123")
        assert len(results) == 0


class TestTopComments:
    def test_top_by_likes(self):
        video = _make_video()
        top = top_comments(video, n=3)
        assert len(top) == 3
        # Should be sorted by likes descending
        assert top[0].likes >= top[1].likes >= top[2].likes
        assert top[0].likes == 100  # c4 has 100 likes

    def test_top_by_length(self):
        video = _make_video()
        top = top_comments(video, n=2, by="length")
        assert len(top) == 2
        assert len(top[0].text) >= len(top[1].text)

    def test_top_n_larger_than_comments(self):
        video = _make_video()
        top = top_comments(video, n=100)
        assert len(top) == 5  # All comments

    def test_empty_comments(self):
        video = _make_video(comments=[])
        top = top_comments(video, n=5)
        assert len(top) == 0
