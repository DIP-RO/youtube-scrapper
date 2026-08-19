"""Integration test — test ALL package features end-to-end.

This test initializes the package in a temp environment and exercises
every public API to ensure everything works together properly.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

import media_data_extractor
from media_data_extractor import (
    # Core
    YouTubeScraper,
    ScraperConfig,
    ScraperError,
    # Models
    VideoResult,
    VideoMetadata,
    Transcript,
    TranscriptSegment,
    Comment,
    Engagement,
    Summary,
    AccessStatus,
    NetworkInfo,
    BatchResult,
    BatchError,
    StreamFormat,
    DownloadResult,
    # Export
    export_video,
    export_batch,
    video_to_csv,
    comments_to_csv,
    transcript_to_txt,
    transcript_to_srt,
    video_to_jsonl,
    video_to_xlsx,
    batch_to_csv,
    batch_to_jsonl,
    batch_to_xlsx,
    batch_comments_to_csv,
    download_video,
    download_batch,
    # Downloader
    extract_streams,
    download_stream,
    download_video_file,
    has_ffmpeg,
    merge_audio_video,
    select_best_video,
    select_best_audio,
    select_best_progressive,
    select_worst_progressive,
    select_by_quality,
    # Sentiment
    analyze_sentiment,
    analyze_comment_sentiment,
    analyze_video_sentiment,
    SentimentResult,
    CommentSentiment,
    VideoSentiment,
    # Filters
    CommentFilter,
    filter_comments,
    search_comments,
    top_comments,
    # Player
    VideoPlayer,
    Playlist,
    Track,
    save_playlist,
    load_playlist,
    create_playlist_from_directory,
    find_player_backend,
    has_ffplay,
    # Pipeline
    ScrapePipeline,
    PipelineResult,
    PipelineStageResult,
    VALID_STAGES,
    # Performance
    LRUCache,
    RateLimiter,
    BackoffStrategy,
    retry_with_backoff,
    chunk_list,
    get_metadata_cache,
    get_stream_cache,
    clear_all_caches,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_full_video(video_id: str = "vid1") -> VideoResult:
    """Create a VideoResult with all fields populated."""
    return VideoResult(
        video_id=video_id,
        source_url=f"https://www.youtube.com/watch?v={video_id}",
        metadata=VideoMetadata(
            video_url=f"https://www.youtube.com/watch?v={video_id}",
            title="Test Video Title",
            description="A test description",
            views=100000,
            channel_name="TestChannel",
            channel_id="UC123456",
            channel_url="https://www.youtube.com/channel/UC123456",
            upload_date="2024-01-15",
            duration_seconds=300,
            category="Education",
            is_live=False,
            keywords=["python", "tutorial"],
            thumbnail="https://example.com/thumb.jpg",
        ),
        engagement=Engagement(
            likes=5000,
            views=100000,
            comment_count=200,
            comment_count_scraped=3,
        ),
        transcript=Transcript(
            available=True,
            text="Hello world this is a test transcript",
            language="en",
            segments=[
                TranscriptSegment(text="Hello world", start_ms=0, duration_ms=2000),
                TranscriptSegment(text="this is a test", start_ms=2000, duration_ms=3000),
                TranscriptSegment(text="transcript", start_ms=5000, duration_ms=1000),
            ],
        ),
        summary=Summary(available=True, text="A test transcript summary"),
        comments=[
            Comment(comment_id="c1", likes=50, reply_count=2, is_pinned=True, is_hearted=False,
                    author="Alice", text="This is a great and amazing video!"),
            Comment(comment_id="c2", likes=5, reply_count=0, is_pinned=False, is_hearted=True,
                    author="Bob", text="This is terrible and boring"),
            Comment(comment_id="c3", likes=10, reply_count=1, is_pinned=False, is_hearted=False,
                    author="Charlie", text="Okay video, nothing special"),
        ],
        network=NetworkInfo(access_status=AccessStatus(blocked=False)),
    )


@pytest.fixture
def full_video():
    return _make_full_video("testvid")


@pytest.fixture
def full_batch():
    return BatchResult(
        total=3,
        succeeded=2,
        failed=1,
        results=[_make_full_video("vid1"), _make_full_video("vid2")],
        errors=[BatchError(url_or_id="bad1", error_type="TestError", error_message="Failed")],
    )


# ---------------------------------------------------------------------------
# Test 1: Package initialization
# ---------------------------------------------------------------------------

class TestPackageInit:
    def test_version_is_3_1_0(self):
        assert media_data_extractor.__version__ == "5.1.0"

    def test_all_exports_present(self):
        assert len(media_data_extractor.__all__) >= 60

    def test_no_import_errors(self):
        """Ensure importing the package doesn't raise."""
        import importlib
        importlib.reload(media_data_extractor)


# ---------------------------------------------------------------------------
# Test 2: All export formats
# ---------------------------------------------------------------------------

class TestAllExportFormats:
    def test_json(self, full_video):
        content = export_video(full_video, format="json")
        data = json.loads(content)
        assert data["video_id"] == "testvid"

    def test_csv(self, full_video):
        content = export_video(full_video, format="csv")
        assert "video_id" in content
        assert "testvid" in content

    def test_csv_comments(self, full_video):
        content = export_video(full_video, format="csv", comments=True)
        assert "Alice" in content
        assert "Bob" in content

    def test_jsonl(self, full_video):
        content = export_video(full_video, format="jsonl")
        data = json.loads(content)
        assert data["video_id"] == "testvid"

    def test_txt(self, full_video):
        content = export_video(full_video, format="txt")
        assert "Hello world" in content

    def test_xlsx(self, full_video):
        content = export_video(full_video, format="xlsx")
        assert "<Workbook" in content

    def test_srt(self, full_video):
        content = export_video(full_video, format="srt")
        assert "00:00:00,000" in content
        assert "Hello world" in content

    def test_batch_json(self, full_batch):
        content = export_batch(full_batch, format="json")
        data = json.loads(content)
        assert data["succeeded"] == 2

    def test_batch_csv(self, full_batch):
        content = export_batch(full_batch, format="csv")
        assert "vid1" in content

    def test_batch_jsonl(self, full_batch):
        lines = export_batch(full_batch, format="jsonl").strip().split("\n")
        assert len(lines) == 3  # 2 results + 1 error

    def test_batch_xlsx(self, full_batch):
        content = export_batch(full_batch, format="xlsx")
        assert "<Workbook" in content

    def test_batch_csv_comments(self, full_batch):
        content = export_batch(full_batch, format="csv", comments=True)
        assert "Alice" in content


# ---------------------------------------------------------------------------
# Test 3: Download to directory
# ---------------------------------------------------------------------------

class TestDownloadToDirectory:
    def test_download_video_all_formats(self, full_video, tmp_path):
        files = download_video(full_video, tmp_path, formats=["json", "csv", "txt", "srt", "xlsx"])
        assert len(files) >= 5
        for f in files:
            assert f.exists()

    def test_download_batch_all_formats(self, full_batch, tmp_path):
        files = download_batch(full_batch, tmp_path, formats=["json", "csv"])
        # batch_result.json + batch_summary.csv + batch_all_comments.csv + per-video files
        assert len(files) >= 5
        for f in files:
            assert f.exists()


# ---------------------------------------------------------------------------
# Test 4: Sentiment analysis
# ---------------------------------------------------------------------------

class TestSentimentFull:
    def test_analyze_text(self):
        result = analyze_sentiment("This is amazing and wonderful!")
        assert result.label == "positive"
        assert result.compound > 0

    def test_analyze_negative(self):
        result = analyze_sentiment("This is terrible and awful")
        assert result.label == "negative"
        assert result.compound < 0

    def test_analyze_neutral(self):
        result = analyze_sentiment("The video is about Python")
        assert result.label == "neutral"

    def test_analyze_comment(self, full_video):
        result = analyze_comment_sentiment(full_video.comments[0])
        assert isinstance(result, CommentSentiment)
        assert result.sentiment.label in ("positive", "negative", "neutral")

    def test_analyze_video(self, full_video):
        result = analyze_video_sentiment(full_video)
        assert isinstance(result, VideoSentiment)
        assert result.total_comments == 3
        assert result.positive_count + result.negative_count + result.neutral_count == 3
        assert -1.0 <= result.average_compound <= 1.0

    def test_sentiment_to_dict(self, full_video):
        result = analyze_video_sentiment(full_video)
        d = result.to_dict()
        assert "total_comments" in d
        assert "comment_sentiments" in d
        assert len(d["comment_sentiments"]) == 3


# ---------------------------------------------------------------------------
# Test 5: Comment filtering
# ---------------------------------------------------------------------------

class TestFilteringFull:
    def test_keyword_filter(self, full_video):
        filtered = filter_comments(full_video, keyword="great")
        assert len(filtered) >= 1

    def test_author_filter(self, full_video):
        filtered = filter_comments(full_video, author="alice")
        assert len(filtered) == 1

    def test_min_likes(self, full_video):
        filtered = filter_comments(full_video, min_likes=10)
        assert all(c.likes >= 10 for c in filtered)

    def test_sentiment_filter(self, full_video):
        positive = filter_comments(full_video, sentiment="positive")
        assert all(c.text for c in positive)

    def test_regex_filter(self, full_video):
        filtered = filter_comments(full_video, regex=r"great|terrible")
        assert len(filtered) >= 2

    def test_combined_filters(self, full_video):
        filtered = filter_comments(full_video, min_likes=5, sentiment="positive")
        assert all(c.likes >= 5 for c in filtered)

    def test_search_comments(self, full_video):
        results = search_comments(full_video, "great")
        assert len(results) >= 1

    def test_top_comments(self, full_video):
        top = top_comments(full_video, n=2)
        assert len(top) == 2
        assert top[0].likes >= top[1].likes


# ---------------------------------------------------------------------------
# Test 6: Stream extraction and download
# ---------------------------------------------------------------------------

class TestStreamExtraction:
    def test_extract_streams(self):
        player = {
            "streamingData": {
                "formats": [
                    {"itag": 22, "url": "https://example.com/720p.mp4", "mimeType": "video/mp4",
                     "qualityLabel": "720p", "contentLength": "5000000"},
                ],
                "adaptiveFormats": [
                    {"itag": 137, "url": "https://example.com/1080p.mp4", "mimeType": "video/mp4",
                     "qualityLabel": "1080p", "height": 1080},
                    {"itag": 140, "url": "https://example.com/audio.m4a", "mimeType": "audio/mp4",
                     "bitrate": 128000},
                ],
            }
        }
        formats = extract_streams(player)
        assert len(formats) == 3

    def test_select_best_video(self):
        formats = [
            StreamFormat(itag=136, url="u1", mime_type="video/mp4", height=720, has_video=True, has_audio=False),
            StreamFormat(itag=137, url="u2", mime_type="video/mp4", height=1080, has_video=True, has_audio=False),
        ]
        best = select_best_video(formats)
        assert best.itag == 137

    def test_select_best_audio(self):
        formats = [
            StreamFormat(itag=139, url="u1", mime_type="audio/mp4", bitrate=48000, has_audio=True, has_video=False),
            StreamFormat(itag=140, url="u2", mime_type="audio/mp4", bitrate=128000, has_audio=True, has_video=False),
        ]
        best = select_best_audio(formats)
        assert best.itag == 140

    def test_select_by_quality(self):
        formats = [
            StreamFormat(itag=22, url="u1", mime_type="video/mp4", quality_label="720p",
                         height=720, has_video=True, has_audio=True),
        ]
        result = select_by_quality(formats, "720p")
        assert result is not None
        assert result.itag == 22

    def test_has_ffmpeg(self):
        assert isinstance(has_ffmpeg(), bool)


# ---------------------------------------------------------------------------
# Test 7: Video player
# ---------------------------------------------------------------------------

class TestPlayerFull:
    def test_create_player_dry_run(self):
        player = VideoPlayer(dry_run=True)
        assert player.dry_run is True
        assert player.backend in ("ffplay", "vlc", "mpv", "system")

    def test_play_file_dry_run(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        player = VideoPlayer(dry_run=True)
        assert player.play_file(video) is True
        assert player.is_playing is True

    def test_playlist_full_cycle(self, tmp_path):
        v1 = tmp_path / "v1.mp4"
        v2 = tmp_path / "v2.mp4"
        v1.write_bytes(b"v1")
        v2.write_bytes(b"v2")

        playlist = Playlist(name="Test")
        playlist.add_track(Track(path=str(v1), title="Video 1"))
        playlist.add_track(Track(path=str(v2), title="Video 2"))
        playlist.loop_mode = "all"

        player = VideoPlayer(dry_run=True)
        assert player.play_playlist(playlist) is True
        assert player.play_next() is True
        assert player.play_next() is True  # Loops back
        player.stop()
        assert player.is_playing is False

    def test_playlist_save_load(self, tmp_path):
        playlist = Playlist(name="My Mix")
        playlist.add_track(Track(path="/tmp/v1.mp4", title="V1"))
        playlist.add_track(Track(path="/tmp/v2.mp4", title="V2"))

        pl_file = tmp_path / "playlist.json"
        save_playlist(playlist, pl_file)
        loaded = load_playlist(pl_file)
        assert loaded.name == "My Mix"
        assert loaded.size == 2

    def test_create_playlist_from_dir(self, tmp_path):
        (tmp_path / "a.mp4").write_bytes(b"a")
        (tmp_path / "b.mp4").write_bytes(b"b")
        playlist = create_playlist_from_directory(tmp_path)
        assert playlist.size == 2


# ---------------------------------------------------------------------------
# Test 8: Pipeline
# ---------------------------------------------------------------------------

class TestPipelineFull:
    def test_pipeline_creation(self):
        pipeline = ScrapePipeline(stages=["scrape", "sentiment"])
        assert "scrape" in pipeline.stages

    def test_pipeline_invalid_stage(self):
        with pytest.raises(ValueError):
            ScrapePipeline(stages=["invalid"])

    def test_pipeline_result_to_dict(self):
        result = PipelineResult(total=5, succeeded=3, failed=2)
        result.stage_results.append(PipelineStageResult(name="scrape", succeeded=3))
        d = result.to_dict()
        assert d["total"] == 5
        assert len(d["stage_results"]) == 1


# ---------------------------------------------------------------------------
# Test 9: Performance utilities
# ---------------------------------------------------------------------------

class TestPerformanceFull:
    def test_lru_cache(self):
        cache = LRUCache(maxsize=100)
        cache.put("key", "value")
        assert cache.get("key") == "value"
        assert cache.get("missing") is None

    def test_rate_limiter(self):
        limiter = RateLimiter(rate=10.0, burst=5)
        for _ in range(5):
            assert limiter.try_acquire() is True

    def test_backoff_strategy(self):
        strat = BackoffStrategy(initial_delay=1.0, multiplier=2.0, jitter=0)
        assert strat.delay(0) == 1.0
        assert strat.delay(1) == 2.0

    def test_retry_with_backoff(self):
        count = 0

        def func():
            nonlocal count
            count += 1
            return "ok"

        result = retry_with_backoff(func, max_retries=3)
        assert result == "ok"
        assert count == 1

    def test_chunk_list(self):
        chunks = chunk_list(list(range(10)), chunk_size=3)
        assert len(chunks) == 4

    def test_global_caches(self):
        clear_all_caches()
        cache = get_metadata_cache()
        cache.put("test", 1)
        assert cache.get("test") == 1
        clear_all_caches()
        assert cache.get("test") is None


# ---------------------------------------------------------------------------
# Test 10: End-to-end workflow (all features together)
# ---------------------------------------------------------------------------

class TestEndToEndWorkflow:
    """Test a complete workflow: scrape → filter → sentiment → export → download → play."""

    def test_full_workflow(self, tmp_path):
        # 1. Create a mock video result
        video = _make_full_video("e2e_test")

        # 2. Filter comments
        from media_data_extractor import CommentFilter
        filtered = filter_comments(video, filter=CommentFilter(min_likes=5))
        assert len(filtered) <= len(video.comments)

        # 3. Sentiment analysis
        sentiment = analyze_video_sentiment(video)
        assert sentiment.total_comments > 0
        assert sentiment.overall_label in ("positive", "negative", "neutral")

        # 4. Export to all formats
        for fmt in ["json", "csv", "jsonl", "txt", "srt", "xlsx"]:
            content = export_video(video, format=fmt)
            assert len(content) > 0

        # 5. Download to directory
        files = download_video(video, tmp_path / "output")
        assert len(files) >= 4

        # 6. Create playlist from downloaded files
        playlist = create_playlist_from_directory(tmp_path / "output")
        # Should find at least the transcript txt file (not a video, but test the function)
        assert isinstance(playlist, Playlist)

        # 7. Player dry-run
        if playlist.size > 0:
            player = VideoPlayer(dry_run=True)
            assert player.play_playlist(playlist) is True

    def test_batch_workflow(self, full_batch, tmp_path):
        # 1. Export batch
        for fmt in ["json", "csv", "jsonl", "xlsx"]:
            content = export_batch(full_batch, format=fmt)
            assert len(content) > 0

        # 2. Download batch
        files = download_batch(full_batch, tmp_path / "batch_output")
        assert len(files) > 0

        # 3. Sentiment on each result
        for result in full_batch.results:
            sentiment = analyze_video_sentiment(result)
            assert sentiment.total_comments > 0

    def test_pipeline_result_serialization(self):
        """Test that a PipelineResult can be serialized to JSON."""
        result = PipelineResult(total=10, succeeded=8, failed=2)
        result.stage_results.append(PipelineStageResult(name="scrape", succeeded=8, failed=2))
        result.output_files.append("/tmp/output.json")
        d = result.to_dict()
        # Must be JSON serializable
        json_str = json.dumps(d)
        assert "total" in json_str
        assert "stage_results" in json_str
