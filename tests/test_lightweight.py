"""Tests for lightweight import optimization and lazy loading."""

from __future__ import annotations

import importlib
import sys
import time

import pytest


class TestLightweightImports:
    """Verify that heavy modules are not loaded on basic import."""

    @pytest.fixture(autouse=True)
    def save_restore_modules(self):
        """Save sys.modules state and restore after each test."""
        saved = sys.modules.copy()
        yield
        # Restore: remove any new modules, re-add any removed ones
        current = set(sys.modules.keys())
        saved_keys = set(saved.keys())
        # Remove modules that weren't in the saved state
        for key in current - saved_keys:
            del sys.modules[key]
        # Re-add modules that were in the saved state
        for key in saved_keys - current:
            sys.modules[key] = saved[key]
        # Restore any modules that were replaced
        for key in saved_keys & current:
            sys.modules[key] = saved[key]

    def _clear_package(self):
        """Remove all media_data_extractor modules from sys.modules."""
        for m in list(sys.modules.keys()):
            if "media_data_extractor" in m:
                del sys.modules[m]

    def test_core_import_is_lightweight(self):
        """core.py should not load heavy modules."""
        self._clear_package()
        from media_data_extractor.core import YouTubeScraper

        loaded = [m for m in sys.modules if "media_data_extractor" in m]
        heavy = {"media_data_extractor.platforms.youtube.downloader", "media_data_extractor.exporters._all",
                 "media_data_extractor.analytics.sentiment", "media_data_extractor.analytics.filters",
                 "media_data_extractor.media.player", "media_data_extractor.media.pipeline",
                 "media_data_extractor.analytics.research", "media_data_extractor.utils.performance"}
        assert not heavy.intersection(loaded), f"Heavy modules loaded: {heavy.intersection(loaded)}"

    def test_init_import_is_lightweight(self):
        """__init__.py should not load heavy modules on import."""
        self._clear_package()
        import media_data_extractor

        loaded = [m for m in sys.modules if "media_data_extractor" in m]
        heavy = {"media_data_extractor.platforms.youtube.downloader", "media_data_extractor.exporters._all",
                 "media_data_extractor.analytics.sentiment", "media_data_extractor.analytics.filters",
                 "media_data_extractor.media.player", "media_data_extractor.media.pipeline",
                 "media_data_extractor.analytics.research", "media_data_extractor.utils.performance"}
        assert not heavy.intersection(loaded), f"Heavy modules loaded: {heavy.intersection(loaded)}"

    def test_lazy_load_on_access(self):
        """Heavy modules should load on first attribute access."""
        self._clear_package()
        import media_data_extractor

        assert "media_data_extractor.media.player" not in sys.modules
        player = media_data_extractor.VideoPlayer
        assert "media_data_extractor.media.player" in sys.modules
        assert player is not None

    def test_lazy_load_caches_in_globals(self):
        """Lazy-loaded attributes should be cached in globals."""
        self._clear_package()
        import media_data_extractor

        player1 = media_data_extractor.VideoPlayer
        player2 = media_data_extractor.VideoPlayer
        assert player1 is player2

    def test_lazy_load_research(self):
        """Research module should load lazily."""
        self._clear_package()
        import media_data_extractor

        assert "media_data_extractor.analytics.research" not in sys.modules
        func = media_data_extractor.collect_dataset
        assert "media_data_extractor.analytics.research" in sys.modules
        assert callable(func)

    def test_lazy_load_downloader(self):
        """Downloader module should load lazily."""
        self._clear_package()
        import media_data_extractor

        assert "media_data_extractor.platforms.youtube.downloader" not in sys.modules
        func = media_data_extractor.extract_streams
        assert "media_data_extractor.platforms.youtube.downloader" in sys.modules
        assert callable(func)

    def test_lazy_load_sentiment(self):
        """Sentiment module should load lazily."""
        self._clear_package()
        import media_data_extractor

        assert "media_data_extractor.analytics.sentiment" not in sys.modules
        func = media_data_extractor.analyze_sentiment
        assert "media_data_extractor.analytics.sentiment" in sys.modules
        assert callable(func)

    def test_lazy_load_export(self):
        """Export module should load lazily."""
        self._clear_package()
        import media_data_extractor

        assert "media_data_extractor.exporters._all" not in sys.modules
        func = media_data_extractor.export_video
        assert "media_data_extractor.exporters._all" in sys.modules
        assert callable(func)

    def test_lazy_load_performance(self):
        """Performance module should load lazily."""
        self._clear_package()
        import media_data_extractor

        assert "media_data_extractor.utils.performance" not in sys.modules
        cls = media_data_extractor.LRUCache
        assert "media_data_extractor.utils.performance" in sys.modules

    def test_lazy_load_pipeline(self):
        """Pipeline module should load lazily."""
        self._clear_package()
        import media_data_extractor

        assert "media_data_extractor.media.pipeline" not in sys.modules
        cls = media_data_extractor.ScrapePipeline
        assert "media_data_extractor.media.pipeline" in sys.modules

    def test_lazy_load_filters(self):
        """Filters module should load lazily."""
        self._clear_package()
        import media_data_extractor

        assert "media_data_extractor.analytics.filters" not in sys.modules
        cls = media_data_extractor.CommentFilter
        assert "media_data_extractor.analytics.filters" in sys.modules

    def test_dir_includes_lazy_exports(self):
        """__dir__() should include all lazy exports for tab-completion."""
        import media_data_extractor
        all_names = set(dir(media_data_extractor))
        assert "YouTubeScraper" in all_names
        assert "VideoPlayer" in all_names
        assert "collect_dataset" in all_names
        assert "ScrapePipeline" in all_names

    def test_attribute_error_for_unknown(self):
        """Unknown attributes should raise AttributeError."""
        import media_data_extractor
        with pytest.raises(AttributeError, match="has no attribute"):
            _ = media_data_extractor.nonexistent_thing

    def test_core_module_exports(self):
        """core.py should export the essential classes."""
        from media_data_extractor import core

        assert hasattr(core, "YouTubeScraper")
        assert hasattr(core, "ScraperConfig")
        assert hasattr(core, "VideoResult")
        assert hasattr(core, "BatchResult")
        assert not hasattr(core, "VideoPlayer")
        assert not hasattr(core, "collect_dataset")
        assert not hasattr(core, "ScrapePipeline")

    def test_import_time_under_200ms(self):
        """Package import should be fast (< 200ms)."""
        self._clear_package()
        import json
        import re

        t0 = time.perf_counter()
        import media_data_extractor
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000
        assert elapsed_ms < 200, f"Import took {elapsed_ms:.1f}ms, expected < 200ms"

    def test_core_import_time_under_100ms(self):
        """Core import should be very fast (< 100ms on warm cache)."""
        self._clear_package()
        import json
        import re
        import requests

        t0 = time.perf_counter()
        from media_data_extractor.core import YouTubeScraper
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000
        assert elapsed_ms < 100, f"Core import took {elapsed_ms:.1f}ms, expected < 100ms"

    def test_all_exports_accessible(self):
        """Every name in __all__ should be accessible (lazy or eager)."""
        import media_data_extractor
        for name in media_data_extractor.__all__:
            attr = getattr(media_data_extractor, name)
            assert attr is not None, f"{name} is None"

    def test_selenium_not_imported_at_package_level(self):
        """Selenium should not be imported until YouTubeScraper.__enter__."""
        self._clear_package()
        import media_data_extractor
        assert "selenium" not in sys.modules
