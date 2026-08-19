"""Tests for the video player module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from media_data_extractor.media.player import (
    Playlist,
    Track,
    VideoPlayer,
    create_playlist_from_directory,
    find_player_backend,
    has_ffplay,
    load_playlist,
    save_playlist,
)


class TestTrack:
    def test_track_creation(self):
        track = Track(path="/tmp/video.mp4", title="My Video")
        assert track.path == "/tmp/video.mp4"
        assert track.title == "My Video"

    def test_track_filename(self):
        track = Track(path="/tmp/video.mp4")
        assert track.filename == "video.mp4"

    def test_track_default_title_is_empty(self):
        track = Track(path="/tmp/video.mp4")
        assert track.title == ""

    def test_track_to_dict(self):
        track = Track(path="/tmp/video.mp4", title="Test", video_id="vid1")
        d = track.to_dict()
        assert d["path"] == "/tmp/video.mp4"
        assert d["title"] == "Test"
        assert d["video_id"] == "vid1"

    def test_track_from_dict(self):
        d = {"path": "/tmp/v.mp4", "title": "Test", "video_id": "abc"}
        track = Track.from_dict(d)
        assert track.path == "/tmp/v.mp4"
        assert track.title == "Test"
        assert track.video_id == "abc"

    def test_track_from_dict_defaults(self):
        d = {"path": "/tmp/v.mp4"}
        track = Track.from_dict(d)
        assert track.path == "/tmp/v.mp4"
        assert track.title == ""
        assert track.duration_seconds is None


class TestPlaylist:
    def _make_playlist(self, n: int = 3) -> Playlist:
        pl = Playlist(name="Test")
        for i in range(n):
            pl.add_track(Track(path=f"/tmp/video{i}.mp4", title=f"Video {i}"))
        return pl

    def test_empty_playlist(self):
        pl = Playlist()
        assert pl.is_empty
        assert pl.size == 0
        assert pl.current_track is None

    def test_add_track(self):
        pl = Playlist()
        pl.add_track(Track(path="/tmp/v1.mp4"))
        assert pl.size == 1
        assert not pl.is_empty

    def test_add_tracks(self):
        pl = Playlist()
        pl.add_tracks([Track(path="/tmp/v1.mp4"), Track(path="/tmp/v2.mp4")])
        assert pl.size == 2

    def test_remove_track(self):
        pl = self._make_playlist(3)
        removed = pl.remove_track(1)
        assert removed is not None
        assert pl.size == 2

    def test_remove_track_invalid_index(self):
        pl = self._make_playlist(3)
        removed = pl.remove_track(99)
        assert removed is None
        assert pl.size == 3

    def test_clear(self):
        pl = self._make_playlist(3)
        pl.clear()
        assert pl.is_empty
        assert pl.size == 0

    def test_current_track(self):
        pl = self._make_playlist(3)
        assert pl.current_track is not None
        assert pl.current_track.path == "/tmp/video0.mp4"

    def test_next_track(self):
        pl = self._make_playlist(3)
        assert pl.next_track is not None
        assert pl.next_track.path == "/tmp/video1.mp4"

    def test_next_track_at_end_no_loop(self):
        pl = self._make_playlist(2)
        pl.current_index = 1
        assert pl.next_track is None

    def test_next_track_at_end_loop_all(self):
        pl = self._make_playlist(2)
        pl.loop_mode = "all"
        pl.current_index = 1
        assert pl.next_track is not None
        assert pl.next_track.path == "/tmp/video0.mp4"

    def test_next_track_loop_one(self):
        pl = self._make_playlist(3)
        pl.loop_mode = "one"
        assert pl.next_track == pl.current_track

    def test_previous_track(self):
        pl = self._make_playlist(3)
        pl.current_index = 2
        assert pl.previous_track is not None
        assert pl.previous_track.path == "/tmp/video1.mp4"

    def test_previous_track_at_start_no_loop(self):
        pl = self._make_playlist(3)
        pl.current_index = 0
        assert pl.previous_track is None

    def test_previous_track_at_start_loop_all(self):
        pl = self._make_playlist(3)
        pl.loop_mode = "all"
        pl.current_index = 0
        assert pl.previous_track is not None
        assert pl.previous_track.path == "/tmp/video2.mp4"

    def test_advance(self):
        pl = self._make_playlist(3)
        track = pl.advance()
        assert track is not None
        assert pl.current_index == 1

    def test_advance_at_end_no_loop(self):
        pl = self._make_playlist(2)
        pl.current_index = 1
        track = pl.advance()
        assert track is None

    def test_advance_at_end_loop_all(self):
        pl = self._make_playlist(2)
        pl.loop_mode = "all"
        pl.current_index = 1
        track = pl.advance()
        assert track is not None
        assert pl.current_index == 0

    def test_advance_loop_one(self):
        pl = self._make_playlist(3)
        pl.loop_mode = "one"
        track = pl.advance()
        assert track == pl.current_track
        assert pl.current_index == 0

    def test_go_back(self):
        pl = self._make_playlist(3)
        pl.current_index = 2
        track = pl.go_back()
        assert track is not None
        assert pl.current_index == 1

    def test_go_back_at_start(self):
        pl = self._make_playlist(3)
        pl.current_index = 0
        track = pl.go_back()
        assert pl.current_index == 0

    def test_shuffle(self):
        pl = self._make_playlist(10)
        pl.shuffle()
        assert pl.shuffled is True

    def test_unshuffle(self):
        pl = self._make_playlist(10)
        pl.shuffle()
        pl.unshuffle()
        assert pl.shuffled is False

    def test_to_dict(self):
        pl = self._make_playlist(2)
        d = pl.to_dict()
        assert d["name"] == "Test"
        assert len(d["tracks"]) == 2
        assert d["current_index"] == 0

    def test_from_dict(self):
        d = {
            "name": "Loaded",
            "tracks": [{"path": "/tmp/v.mp4", "title": "V"}],
            "current_index": 0,
            "loop_mode": "all",
            "shuffled": False,
        }
        pl = Playlist.from_dict(d)
        assert pl.name == "Loaded"
        assert pl.size == 1
        assert pl.loop_mode == "all"


class TestVideoPlayer:
    def test_dry_run_play_file(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake video")
        player = VideoPlayer(dry_run=True)
        assert player.play_file(video) is True
        assert player.is_playing is True
        assert player.current_track is not None

    def test_play_nonexistent_file(self):
        player = VideoPlayer(dry_run=True)
        assert player.play_file("/nonexistent/file.mp4") is False

    def test_dry_run_play_playlist(self, tmp_path):
        v1 = tmp_path / "v1.mp4"
        v2 = tmp_path / "v2.mp4"
        v1.write_bytes(b"v1")
        v2.write_bytes(b"v2")
        playlist = Playlist(name="Test")
        playlist.add_track(Track(path=str(v1)))
        playlist.add_track(Track(path=str(v2)))
        player = VideoPlayer(dry_run=True)
        assert player.play_playlist(playlist) is True
        assert player.is_playing is True

    def test_play_empty_playlist(self):
        playlist = Playlist()
        player = VideoPlayer(dry_run=True)
        assert player.play_playlist(playlist) is False

    def test_dry_run_play_next(self, tmp_path):
        v1 = tmp_path / "v1.mp4"
        v2 = tmp_path / "v2.mp4"
        v1.write_bytes(b"v1")
        v2.write_bytes(b"v2")
        playlist = Playlist(name="Test")
        playlist.add_track(Track(path=str(v1)))
        playlist.add_track(Track(path=str(v2)))
        player = VideoPlayer(dry_run=True)
        player.play_playlist(playlist)
        assert player.play_next() is True
        assert player.current_track.path == str(v2)

    def test_dry_run_play_next_at_end(self, tmp_path):
        v1 = tmp_path / "v1.mp4"
        v1.write_bytes(b"v1")
        playlist = Playlist(name="Test")
        playlist.add_track(Track(path=str(v1)))
        player = VideoPlayer(dry_run=True)
        player.play_playlist(playlist)
        assert player.play_next() is False

    def test_dry_run_play_previous(self, tmp_path):
        v1 = tmp_path / "v1.mp4"
        v2 = tmp_path / "v2.mp4"
        v1.write_bytes(b"v1")
        v2.write_bytes(b"v2")
        playlist = Playlist(name="Test")
        playlist.add_track(Track(path=str(v1)))
        playlist.add_track(Track(path=str(v2)))
        player = VideoPlayer(dry_run=True)
        player.play_playlist(playlist)
        player.play_next()
        assert player.play_previous() is True
        assert player.current_track.path == str(v1)

    def test_stop(self, tmp_path):
        v1 = tmp_path / "v1.mp4"
        v1.write_bytes(b"v1")
        player = VideoPlayer(dry_run=True)
        player.play_file(v1)
        player.stop()
        assert player.is_playing is False
        assert player.current_track is None

    def test_pause_resume_dry_run(self, tmp_path):
        v1 = tmp_path / "v1.mp4"
        v1.write_bytes(b"v1")
        player = VideoPlayer(dry_run=True)
        player.play_file(v1)
        player.pause()
        assert player.is_paused is True
        player.resume()
        assert player.is_paused is False

    def test_set_volume(self):
        player = VideoPlayer(dry_run=True)
        player.set_volume(50)
        assert player.volume == 50
        player.set_volume(150)
        assert player.volume == 100
        player.set_volume(-10)
        assert player.volume == 0

    def test_elapsed_seconds(self, tmp_path):
        v1 = tmp_path / "v1.mp4"
        v1.write_bytes(b"v1")
        player = VideoPlayer(dry_run=True)
        player.play_file(v1)
        import time
        time.sleep(0.1)
        assert player.elapsed_seconds > 0

    def test_wait_dry_run(self):
        player = VideoPlayer(dry_run=True)
        assert player.wait() == 0


class TestPlaylistIO:
    def test_save_and_load_playlist(self, tmp_path):
        pl = Playlist(name="My Mix")
        pl.add_track(Track(path="/tmp/v1.mp4", title="Video 1"))
        pl.add_track(Track(path="/tmp/v2.mp4", title="Video 2"))
        pl.loop_mode = "all"

        playlist_file = tmp_path / "playlist.json"
        save_playlist(pl, playlist_file)
        assert playlist_file.exists()

        loaded = load_playlist(playlist_file)
        assert loaded.name == "My Mix"
        assert loaded.size == 2
        assert loaded.loop_mode == "all"
        assert loaded.tracks[0].title == "Video 1"

    def test_load_nonexistent_playlist(self):
        with pytest.raises(FileNotFoundError):
            load_playlist("/nonexistent/playlist.json")

    def test_save_creates_parent_dir(self, tmp_path):
        pl = Playlist(name="Test")
        pl.add_track(Track(path="/tmp/v.mp4"))
        save_playlist(pl, tmp_path / "subdir" / "playlist.json")
        assert (tmp_path / "subdir" / "playlist.json").exists()


class TestCreatePlaylistFromDirectory:
    def test_create_from_directory(self, tmp_path):
        (tmp_path / "v1.mp4").write_bytes(b"v1")
        (tmp_path / "v2.mp4").write_bytes(b"v2")
        (tmp_path / "readme.txt").write_text("not a video")
        playlist = create_playlist_from_directory(tmp_path)
        assert playlist.size == 2
        assert all(t.path.endswith(".mp4") for t in playlist.tracks)

    def test_create_from_directory_with_subtitles(self, tmp_path):
        (tmp_path / "v1.mp4").write_bytes(b"v1")
        (tmp_path / "v1.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n")
        playlist = create_playlist_from_directory(tmp_path)
        assert playlist.size == 1
        assert playlist.tracks[0].subtitle_path is not None

    def test_create_from_empty_directory(self, tmp_path):
        playlist = create_playlist_from_directory(tmp_path)
        assert playlist.is_empty

    def test_create_from_nonexistent_directory(self):
        with pytest.raises(FileNotFoundError):
            create_playlist_from_directory("/nonexistent/dir")


class TestPlayerBackend:
    def test_find_player_backend_returns_string_or_none(self):
        backend = find_player_backend()
        assert backend is None or isinstance(backend, str)

    def test_has_ffplay_returns_bool(self):
        assert isinstance(has_ffplay(), bool)
