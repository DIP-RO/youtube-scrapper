"""CLI entry point for media-data-extractor.

Import from here::

    from media_data_extractor.cli import main, build_parser
"""

from __future__ import annotations

from .app import build_parser, main

__all__ = ["main", "build_parser"]
