"""YouTube platform implementation.

Provides YouTubeScraper, ScraperConfig, and YouTube-specific parsing/downloading.

Import from here::

    from media_data_extractor.platforms.youtube import YouTubeScraper, ScraperConfig
"""

from __future__ import annotations

from .scraper import ScraperConfig, YouTubeScraper

__all__ = ["YouTubeScraper", "ScraperConfig"]
