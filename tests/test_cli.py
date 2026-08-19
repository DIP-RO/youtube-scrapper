"""Tests for the CLI in media_data_extractor.cli."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from media_data_extractor.cli import build_parser, main
from media_data_extractor.core.exceptions import InvalidVideoURLError, ScraperError


class TestBuildParser:
    def test_video_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["video", "dQw4w9WgXcQ"])
        assert args.command == "video"
        assert args.url == "dQw4w9WgXcQ"
        assert args.comments == 25
        assert args.lang == "en"
        assert args.timeout == 25

    def test_video_with_options(self):
        parser = build_parser()
        args = parser.parse_args([
            "video", "https://www.youtube.com/watch?v=test",
            "--comments", "100",
            "--lang", "fr",
            "--timeout", "60",
            "--pretty",
        ])
        assert args.comments == 100
        assert args.lang == "fr"
        assert args.timeout == 60
        assert args.pretty is True

    def test_no_command_raises(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_no_headless_flag(self):
        parser = build_parser()
        args = parser.parse_args(["video", "test", "--no-headless"])
        assert args.no_headless is True


class TestMain:
    @patch("media_data_extractor.cli.main.YouTubeScraper")
    def test_video_command_outputs_json(self, mock_scraper_cls):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"video_id": "test", "metadata": {"title": "Test"}}
        mock_scraper = MagicMock()
        mock_scraper.__enter__.return_value = mock_scraper
        mock_scraper.get_video.return_value = mock_result
        mock_scraper_cls.return_value = mock_scraper

        with patch("builtins.print") as mock_print:
            exit_code = main(["video", "dQw4w9WgXcQ"])

        assert exit_code == 0
        mock_scraper.get_video.assert_called_once_with("dQw4w9WgXcQ")
        mock_print.assert_called_once()

    @patch("media_data_extractor.cli.main.YouTubeScraper")
    def test_video_command_writes_to_file(self, mock_scraper_cls, tmp_path):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"video_id": "test"}
        mock_scraper = MagicMock()
        mock_scraper.__enter__.return_value = mock_scraper
        mock_scraper.get_video.return_value = mock_result
        mock_scraper_cls.return_value = mock_scraper

        out_file = tmp_path / "result.json"
        exit_code = main(["video", "dQw4w9WgXcQ", "--out", str(out_file)])

        assert exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["video_id"] == "test"

    @patch("media_data_extractor.cli.main.YouTubeScraper")
    def test_scraper_error_returns_1(self, mock_scraper_cls):
        mock_scraper = MagicMock()
        mock_scraper.__enter__.return_value = mock_scraper
        mock_scraper.get_video.side_effect = InvalidVideoURLError("bad url")
        mock_scraper_cls.return_value = mock_scraper

        with patch("sys.stderr"):
            exit_code = main(["video", "badurl"])

        assert exit_code == 1

    @patch("media_data_extractor.cli.main.YouTubeScraper")
    def test_pretty_flag(self, mock_scraper_cls):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"video_id": "test"}
        mock_scraper = MagicMock()
        mock_scraper.__enter__.return_value = mock_scraper
        mock_scraper.get_video.return_value = mock_result
        mock_scraper_cls.return_value = mock_scraper

        with patch("builtins.print") as mock_print:
            exit_code = main(["video", "dQw4w9WgXcQ", "--pretty"])

        assert exit_code == 0
        # The output should be indented (contains newlines)
        output = mock_print.call_args[0][0]
        assert "\n" in output
