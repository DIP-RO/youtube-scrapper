"""Video player module — play downloaded videos with playlist support.

Provides a developer-friendly video player API inspired by MX Player.
Supports:

- **Single video playback** — play a downloaded video file
- **Playlist management** — create, save, load, and play playlists
- **Playback controls** — play, pause, resume, stop, seek, volume
- **Loop and shuffle** — loop one track, loop all, shuffle
- **Subtitle support** — load SRT subtitles during playback
- **Player backends** — uses ffplay (ffmpeg) or system default player

The player uses subprocess to launch an external video player (ffplay
from ffmpeg, or the OS default). It does not embed a video decoder in
Python — instead it provides a clean programmatic API for controlling
playback that developers can integrate into their applications.

For headless/CI environments, the player can be used in "dry-run" mode
which validates files and simulates playback without launching a process.
"""

from __future__ import annotations

import logging
import os
import random
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Playlist model
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Track:
    """A single track in a playlist.

    Attributes:
        path: File path to the video/audio file.
        title: Display title (defaults to filename).
        duration_seconds: Duration in seconds (if known).
        subtitle_path: Optional SRT subtitle file path.
        video_id: Optional YouTube video ID this track was downloaded from.
    """

    path: str
    title: str = ""
    duration_seconds: float | None = None
    subtitle_path: str | None = None
    video_id: str | None = None

    @property
    def filename(self) -> str:
        return Path(self.path).name

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title or self.filename,
            "duration_seconds": self.duration_seconds,
            "subtitle_path": self.subtitle_path,
            "video_id": self.video_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Track":
        return cls(
            path=d["path"],
            title=d.get("title", ""),
            duration_seconds=d.get("duration_seconds"),
            subtitle_path=d.get("subtitle_path"),
            video_id=d.get("video_id"),
        )


@dataclass(slots=True)
class Playlist:
    """A playlist of video/audio tracks.

    Attributes:
        name: Playlist name.
        tracks: List of Track objects.
        current_index: Index of the currently playing track.
        loop_mode: "none", "one", or "all".
        shuffled: Whether the playlist is shuffled.
    """

    name: str = "Playlist"
    tracks: list[Track] = field(default_factory=list)
    current_index: int = 0
    loop_mode: str = "none"  # "none", "one", "all"
    shuffled: bool = False
    _order: list[int] = field(default_factory=list)

    def add_track(self, track: Track) -> None:
        """Add a track to the end of the playlist."""
        self.tracks.append(track)
        self._rebuild_order()

    def add_tracks(self, tracks: list[Track]) -> None:
        """Add multiple tracks to the playlist."""
        self.tracks.extend(tracks)
        self._rebuild_order()

    def remove_track(self, index: int) -> Track | None:
        """Remove and return the track at *index*."""
        if 0 <= index < len(self.tracks):
            track = self.tracks.pop(index)
            if self.current_index >= len(self.tracks):
                self.current_index = max(0, len(self.tracks) - 1)
            self._rebuild_order()
            return track
        return None

    def clear(self) -> None:
        """Remove all tracks."""
        self.tracks.clear()
        self.current_index = 0
        self._order.clear()

    @property
    def current_track(self) -> Track | None:
        """Return the currently active track, or None."""
        if not self.tracks or self.current_index >= len(self.tracks):
            return None
        return self.tracks[self.current_index]

    @property
    def next_track(self) -> Track | None:
        """Return the next track considering loop mode."""
        if not self.tracks:
            return None
        if self.loop_mode == "one":
            return self.current_track
        next_idx = self.current_index + 1
        if next_idx >= len(self.tracks):
            if self.loop_mode == "all":
                return self.tracks[0]
            return None
        return self.tracks[next_idx]

    @property
    def previous_track(self) -> Track | None:
        """Return the previous track considering loop mode."""
        if not self.tracks:
            return None
        prev_idx = self.current_index - 1
        if prev_idx < 0:
            if self.loop_mode == "all":
                return self.tracks[-1]
            return None
        return self.tracks[prev_idx]

    def advance(self) -> Track | None:
        """Advance to the next track and return it."""
        if not self.tracks:
            return None
        if self.loop_mode == "one":
            return self.current_track
        self.current_index += 1
        if self.current_index >= len(self.tracks):
            if self.loop_mode == "all":
                self.current_index = 0
            else:
                self.current_index = len(self.tracks) - 1
                return None
        return self.current_track

    def go_back(self) -> Track | None:
        """Go to the previous track and return it."""
        if not self.tracks:
            return None
        self.current_index = max(0, self.current_index - 1)
        return self.current_track

    def shuffle(self) -> None:
        """Shuffle the playback order."""
        self.shuffled = True
        self._rebuild_order()

    def unshuffle(self) -> None:
        """Restore original playback order."""
        self.shuffled = False
        self._rebuild_order()

    def _rebuild_order(self) -> None:
        """Rebuild the internal playback order."""
        self._order = list(range(len(self.tracks)))
        if self.shuffled:
            random.shuffle(self._order)

    @property
    def size(self) -> int:
        return len(self.tracks)

    @property
    def is_empty(self) -> bool:
        return len(self.tracks) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tracks": [t.to_dict() for t in self.tracks],
            "current_index": self.current_index,
            "loop_mode": self.loop_mode,
            "shuffled": self.shuffled,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Playlist":
        pl = cls(
            name=d.get("name", "Playlist"),
            tracks=[Track.from_dict(t) for t in d.get("tracks", [])],
            current_index=d.get("current_index", 0),
            loop_mode=d.get("loop_mode", "none"),
            shuffled=d.get("shuffled", False),
        )
        pl._rebuild_order()
        return pl


# ---------------------------------------------------------------------------
# Player backend detection
# ---------------------------------------------------------------------------

def find_player_backend() -> str | None:
    """Find an available video player backend.

    Returns:
        "ffplay" if ffmpeg's ffplay is available.
        "vlc" if VLC is available.
        "system" if an OS default player exists.
        None if no player found.
    """
    if shutil.which("ffplay"):
        return "ffplay"
    if shutil.which("vlc"):
        return "vlc"
    if shutil.which("mpv"):
        return "mpv"
    # OS default — always available on most systems
    return "system"


def has_ffplay() -> bool:
    """Check if ffplay (from ffmpeg) is available."""
    return shutil.which("ffplay") is not None


# ---------------------------------------------------------------------------
# Video Player
# ---------------------------------------------------------------------------

class VideoPlayer:
    """Programmatic video player with playlist support.

    Uses subprocess to launch an external player (ffplay/vlc/mpv/system).
    For headless environments, use ``dry_run=True`` to validate files
    without launching a process.

    Example::

        player = VideoPlayer()
        player.play_file("video.mp4")
        player.wait()

        # Playlist mode
        playlist = Playlist(name="My Mix")
        playlist.add_track(Track(path="video1.mp4"))
        playlist.add_track(Track(path="video2.mp4"))
        player.play_playlist(playlist)
    """

    def __init__(
        self,
        backend: str | None = None,
        volume: int = 100,
        dry_run: bool = False,
    ) -> None:
        """Initialize the video player.

        Args:
            backend: Player backend ("ffplay", "vlc", "mpv", "system").
                If None, auto-detects the best available.
            volume: Initial volume (0-100).
            dry_run: If True, don't launch any process — just validate.
        """
        self.backend = backend or find_player_backend() or "system"
        self.volume = max(0, min(100, volume))
        self.dry_run = dry_run
        self._process: subprocess.Popen | None = None
        self._playlist: Playlist | None = None
        self._current_track: Track | None = None
        self._start_time: float = 0.0
        self._paused: bool = False

    @property
    def is_playing(self) -> bool:
        """Whether a video is currently playing."""
        if self.dry_run:
            return self._current_track is not None and not self._paused
        return self._process is not None and self._process.poll() is None

    @property
    def is_paused(self) -> bool:
        """Whether playback is paused."""
        return self._paused

    @property
    def current_track(self) -> Track | None:
        """The currently playing track."""
        return self._current_track

    @property
    def elapsed_seconds(self) -> float:
        """Seconds since current track started playing."""
        if self._start_time == 0.0:
            return 0.0
        return time.time() - self._start_time

    @property
    def playlist(self) -> Playlist | None:
        """The active playlist, if any."""
        return self._playlist

    # -- Single file playback --------------------------------------------

    def play_file(
        self,
        file_path: str | os.PathLike,
        subtitle_path: str | os.PathLike | None = None,
    ) -> bool:
        """Play a single video file.

        Args:
            file_path: Path to the video file.
            subtitle_path: Optional SRT subtitle file.

        Returns:
            True if playback started successfully.
        """
        path = Path(file_path)
        if not path.exists():
            logger.error("File not found: %s", path)
            return False

        self.stop()
        track = Track(path=str(path), subtitle_path=str(subtitle_path) if subtitle_path else None)
        self._current_track = track
        self._start_time = time.time()
        self._paused = False

        if self.dry_run:
            logger.info("[dry-run] Playing: %s", path)
            return True

        return self._launch_player(str(path), subtitle_path=str(subtitle_path) if subtitle_path else None)

    # -- Playlist playback ------------------------------------------------

    def play_playlist(self, playlist: Playlist, start_index: int = 0) -> bool:
        """Start playing a playlist from a given index.

        Args:
            playlist: The Playlist to play.
            start_index: Index to start from (default: 0).

        Returns:
            True if playback started.
        """
        if playlist.is_empty:
            logger.error("Cannot play empty playlist")
            return False

        playlist.current_index = max(0, min(start_index, playlist.size - 1))
        self._playlist = playlist
        return self._play_current_in_playlist()

    def _play_current_in_playlist(self) -> bool:
        """Play the current track in the active playlist."""
        if not self._playlist or not self._playlist.current_track:
            return False
        track = self._playlist.current_track
        started = self.play_file(track.path, subtitle_path=track.subtitle_path)
        return started

    def play_next(self) -> bool:
        """Skip to the next track in the playlist.

        Returns:
            True if the next track started playing.
        """
        if not self._playlist:
            return False
        track = self._playlist.advance()
        if track is None:
            self.stop()
            return False
        return self._play_current_in_playlist()

    def play_previous(self) -> bool:
        """Go back to the previous track in the playlist.

        Returns:
            True if the previous track started playing.
        """
        if not self._playlist:
            return False
        self._playlist.go_back()
        return self._play_current_in_playlist()

    # -- Playback controls ------------------------------------------------

    def pause(self) -> None:
        """Pause playback (sends SIGSTOP to the player process)."""
        if self._process and self._process.poll() is None:
            try:
                self._process.send_signal(19)  # SIGSTOP
                self._paused = True
                logger.info("Playback paused")
            except Exception as exc:
                logger.warning("Cannot pause: %s", exc)
        else:
            self._paused = True  # dry-run mode

    def resume(self) -> None:
        """Resume paused playback (sends SIGCONT to the player process)."""
        if self._process and self._process.poll() is None:
            try:
                self._process.send_signal(18)  # SIGCONT
                self._paused = False
                logger.info("Playback resumed")
            except Exception as exc:
                logger.warning("Cannot resume: %s", exc)
        else:
            self._paused = False  # dry-run mode

    def stop(self) -> None:
        """Stop playback and terminate the player process."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except (subprocess.TimeoutExpired, Exception):
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        self._current_track = None
        self._paused = False
        self._start_time = 0.0

    def set_volume(self, volume: int) -> None:
        """Set volume (0-100)."""
        self.volume = max(0, min(100, volume))
        logger.info("Volume set to %d%%", self.volume)

    def wait(self, timeout: float | None = None) -> int:
        """Wait for the current playback to finish.

        Args:
            timeout: Maximum seconds to wait. None = wait forever.

        Returns:
            Process return code, or 0 in dry-run mode.
        """
        if self.dry_run:
            return 0
        if self._process is None:
            return 0
        try:
            return self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return -1

    def wait_and_advance(self, timeout: float | None = None) -> bool:
        """Wait for current track to finish, then play next in playlist.

        Args:
            timeout: Maximum seconds to wait per track.

        Returns:
            True if the next track started, False if playlist ended.
        """
        self.wait(timeout=timeout)
        return self.play_next()

    def play_all(self, timeout: float | None = None) -> int:
        """Play through the entire playlist, advancing automatically.

        Args:
            timeout: Maximum seconds per track.

        Returns:
            Number of tracks played.
        """
        if not self._playlist:
            return 0
        count = 0
        while self.is_playing or count == 0:
            self.wait(timeout=timeout)
            count += 1
            if not self.play_next():
                break
        return count

    # -- Backend launcher -------------------------------------------------

    def _launch_player(
        self,
        file_path: str,
        subtitle_path: str | None = None,
    ) -> bool:
        """Launch the video player subprocess.

        Args:
            file_path: Path to the video file.
            subtitle_path: Optional subtitle file.

        Returns:
            True if the process was launched.
        """
        backend = self.backend

        if backend == "ffplay":
            cmd = [
                "ffplay",
                "-nodisp" if False else "-autoexit",  # autoexit closes when done
                "-volume", str(self.volume),
                "-loglevel", "quiet",
            ]
            if subtitle_path:
                cmd.extend(["-vf", f"subtitles={subtitle_path}"])
            cmd.append(file_path)

        elif backend == "vlc":
            cmd = [
                "vlc",
                "--volume", str(self.volume / 100.0),
                "--play-and-exit",
                "--no-video-title-show",
            ]
            if subtitle_path:
                cmd.append(f"--sub-file={subtitle_path}")
            cmd.append(file_path)

        elif backend == "mpv":
            cmd = [
                "mpv",
                f"--volume={self.volume}",
                "--really-quiet",
            ]
            if subtitle_path:
                cmd.append(f"--sub-file={subtitle_path}")
            cmd.append(file_path)

        else:
            # System default — cross-platform
            import platform
            system = platform.system()
            if system == "Darwin":
                cmd = ["open", file_path]
            elif system == "Windows":
                cmd = ["cmd", "/c", "start", "", file_path]
            else:  # Linux and others
                cmd = ["xdg-open", file_path]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Launched %s: %s", backend, file_path)
            return True
        except (FileNotFoundError, OSError) as exc:
            logger.error("Failed to launch %s: %s", backend, exc)
            return False


# ---------------------------------------------------------------------------
# Playlist file I/O
# ---------------------------------------------------------------------------

def save_playlist(playlist: Playlist, path: str | os.PathLike) -> None:
    """Save a playlist to a JSON file.

    Args:
        playlist: The Playlist to save.
        path: Output file path (.json).
    """
    import json

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(playlist.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_playlist(path: str | os.PathLike) -> Playlist:
    """Load a playlist from a JSON file.

    Args:
        path: Path to the playlist JSON file.

    Returns:
        A Playlist object.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file is not valid JSON.
    """
    import json

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Playlist file not found: {path}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return Playlist.from_dict(data)


def create_playlist_from_directory(
    directory: str | os.PathLike,
    name: str = "Directory Playlist",
    extensions: tuple[str, ...] = (".mp4", ".webm", ".mkv", ".avi", ".m4a", ".mp3", ".webm"),
) -> Playlist:
    """Create a playlist from all video/audio files in a directory.

    Args:
        directory: Directory to scan.
        name: Playlist name.
        extensions: File extensions to include.

    Returns:
        A Playlist with all found media files.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")

    playlist = Playlist(name=name)
    for ext in extensions:
        for file_path in sorted(dir_path.glob(f"*{ext}")):
            # Look for matching subtitle file
            subtitle = file_path.with_suffix(".srt")
            playlist.add_track(Track(
                path=str(file_path),
                title=file_path.stem,
                subtitle_path=str(subtitle) if subtitle.exists() else None,
            ))
    return playlist
