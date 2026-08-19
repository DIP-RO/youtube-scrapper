"""Media playback and pipeline orchestration.

Import from here::

    from media_data_extractor.media import VideoPlayer, Playlist, ScrapePipeline
"""

from __future__ import annotations

from .pipeline import (
    PipelineConfig,
    PipelineResult,
    PipelineStageResult,
    ScrapePipeline,
    VALID_STAGES,
)
from .player import (
    Playlist,
    Track,
    VideoPlayer,
    create_playlist_from_directory,
    find_player_backend,
    has_ffplay,
    load_playlist,
    save_playlist,
)

__all__ = [
    "VideoPlayer",
    "Playlist",
    "Track",
    "save_playlist",
    "load_playlist",
    "create_playlist_from_directory",
    "find_player_backend",
    "has_ffplay",
    "ScrapePipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStageResult",
    "VALID_STAGES",
]
