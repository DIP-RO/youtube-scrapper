# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-08-19

### Changed — Industry-Standard Platform-Based Architecture

Major restructure to support multiple social media platforms in the future.
The package now uses a clean, extensible directory structure:

```
media_data_extractor/
├── core/          # Platform-agnostic models, exceptions
├── platforms/     # Platform implementations
│   └── youtube/   # YouTube scraper, parser, downloader
├── exporters/     # CSV, JSON, JSONL, XLSX, SRT, TXT
├── analytics/     # Sentiment, filters, research helpers
├── media/         # Video player, pipeline orchestration
├── utils/         # Performance utilities, helpers
└── cli/           # Command-line interface
```

### Backward Compatibility

All existing imports continue to work unchanged:

```python
from media_data_extractor import YouTubeScraper, ScraperConfig  # ✓
from media_data_extractor.core import YouTubeScraper            # ✓
import media_data_extractor                                      # ✓
```

### New Import Paths (optional)

```python
# Platform-specific
from media_data_extractor.platforms.youtube import YouTubeScraper

# By concern
from media_data_extractor.core import VideoResult, Comment
from media_data_extractor.exporters import export_video
from media_data_extractor.analytics import analyze_sentiment, collect_dataset
from media_data_extractor.media import VideoPlayer, ScrapePipeline
from media_data_extractor.utils import LRUCache, extract_video_id
```

### File Mapping

| Old Location | New Location |
|-------------|-------------|
| `models.py` | `core/models.py` |
| `exceptions.py` | `core/exceptions.py` |
| `client.py` | `platforms/youtube/scraper.py` |
| `parsing.py` | `platforms/youtube/parser.py` |
| `scraper.py` | `platforms/youtube/fetcher.py` |
| `downloader.py` | `platforms/youtube/downloader.py` |
| `export.py` | `exporters/_all.py` |
| `sentiment.py` | `analytics/sentiment.py` |
| `filters.py` | `analytics/filters.py` |
| `research.py` | `analytics/research.py` |
| `player.py` | `media/player.py` |
| `pipeline.py` | `media/pipeline.py` |
| `performance.py` | `utils/performance.py` |
| `utils.py` | `utils/helpers.py` |
| `cli.py` | `cli/main.py` |

### Benefits for Future Development

- Add a new platform (e.g., TikTok) by creating `platforms/tiktok/` — no changes to core
- Clear separation of concerns: models, platform logic, export, analytics
- Each module can be tested and maintained independently
- Industry-standard structure familiar to open-source contributors

521 tests passing, full backward compatibility maintained.

## [4.2.0] - 2026-08-19

### Changed — Lightweight Package Optimization

Major import optimization to make the package lightweight:

- **Lazy imports in `__init__.py`**: `import media_data_extractor` now loads
  only 7 core modules instead of 16. Heavy modules (player, pipeline, research,
  downloader, export, sentiment, filters, performance) load on first attribute
  access via `__getattr__`.
- **New `core` module**: `from media_data_extractor.core import YouTubeScraper`
  provides the absolute lightest import path — only scraping, no optional modules.
- **Lazy selenium**: Selenium is not imported at package import time, only when
  `YouTubeScraper.__enter__()` is called.
- **Lazy downloader**: The downloader module is not imported by `client.py`
  at module level — it loads only when `get_streams()` or
  `download_video_file()` is called.
- **Caching**: Lazy-loaded attributes are cached in module globals after first
  access, so subsequent access has zero overhead.

### Performance

| Metric | Before (v4.1.0) | After (v4.2.0) |
|--------|-----------------|----------------|
| Modules loaded on `import` | 16 | 7 |
| Selenium imported at import time | Yes | No (lazy) |
| Downloader imported by client | Yes | No (lazy) |
| `core` module available | No | Yes |

### Added

- `media_data_extractor.core` — lightweight core API module
- 18 new lightweight import tests (521 total)

## [4.1.0] - 2026-08-18

### Added — Research Data Preparation Module

New `research.py` module with 6 high-level helpers for fast dataset building:

- **`collect_dataset()`** — One call → CSV/JSONL with metadata, engagement, sentiment
- **`collect_comment_corpus()`** — All comments from multiple videos in one CSV for NLP
- **`collect_transcript_corpus()`** — All transcripts in one file for text analysis
- **`collect_comparison_table()`** — Side-by-side comparison with engagement rates
- **`quick_scrape()`** — Fastest way to get data from one video
- **`to_dataframe()` / `batch_to_dataframe()` / `comments_to_dataframe()`** — Pandas integration

Researchers can now prepare datasets in one function call instead of writing
boilerplate scraping, filtering, sentiment, and export code.

- New `research` optional dependency: `pip install media-data-extractor[research]`
- 36 new tests (503 total)

## [4.0.0] - 2026-08-18

### Changed — Package rename (BREAKING)

- **Package renamed** from `yt-network-scraper` to `media-data-extractor`
  - PyPI distribution name: `media-data-extractor`
  - Python import name: `media_data_extractor`
  - Old name `yt-network-scraper` is deprecated and will not receive updates
- **CLI alias**: `mdx` added as a short alias for `media-data-extractor`
  - `mdx video "URL"` works the same as `media-data-extractor video "URL"`
- **SEO keywords** added to PyPI metadata for discoverability
- **Description updated** to reflect full feature set (player, pipeline, sentiment)

### Migration guide

If you were using the old package name:

```python
# Old (deprecated)
from yt_network_scraper import YouTubeScraper

# New (v4.0.0+)
from media_data_extractor import YouTubeScraper
```

```bash
# Old
pip install yt-network-scraper

# New
pip install media-data-extractor
```

```bash
# Old CLI
yt-network-scraper video "URL"

# New CLI
mdx video "URL"
# or
media-data-extractor video "URL"
```

All public API classes, functions, and models remain the same — only the package name changed.

## [3.1.0] - 2026-08-18

### Added — Major release: Video Player, Pipeline, Performance

- **Video Player** (MX Player-style)
  - `VideoPlayer` class with play, pause, resume, stop, seek, volume
  - `Playlist` and `Track` models with loop (none/one/all) and shuffle
  - `save_playlist()` / `load_playlist()` for JSON playlist persistence
  - `create_playlist_from_directory()` — auto-create playlist from media files
  - Subtitle support (SRT files auto-detected)
  - Multiple backends: ffplay, VLC, mpv, system default
  - Dry-run mode for headless/CI validation
  - CLI `player` subcommand
- **Pipeline orchestration**
  - `ScrapePipeline` chains stages: scrape → filter → sentiment → export → download → download_video
  - Each stage is optional and configurable
  - `PipelineResult` with per-stage results, output files, sentiments
  - CLI `pipeline` subcommand with `--stages` flag
- **Performance optimizations for high load**
  - `LRUCache` — thread-safe O(1) get/put with eviction
  - `RateLimiter` — token bucket algorithm, thread-safe
  - `BackoffStrategy` — exponential backoff with jitter
  - `retry_with_backoff()` — retry helper with configurable strategy
  - `chunk_list()` — memory-efficient batch chunking
  - Global caches for metadata and stream URLs
- 154 new tests (467 total)
- Comprehensive integration test covering all package features

### Fixed
- Indentation error in `player.py` `unshuffle()` method

## [2.2.0] - 2026-08-18

### Added — Video File Download
- **Full video download** — download actual YouTube video files to disk
  - `scraper.download_video_file(url, output, quality)` Python API
  - `media-data-extractor download` CLI subcommand
  - Quality selection: best, worst, 720p, 1080p, 4k, audio
  - Progressive format download (combined audio+video, up to 720p)
  - Adaptive format download with ffmpeg merging (1080p+)
  - Audio-only extraction
  - `scraper.get_streams(url)` to list available formats
  - `--list-formats` CLI flag to show available formats without downloading
  - Progress callback for download progress monitoring
- New models: `StreamFormat`, `DownloadResult`
- New module: `downloader.py` with stream extraction and download logic
- 55 new tests (313 total)

### Fixed
- Bug in `_extension_for_mime`: `audio/mp4` was returning `mp4` instead of `m4a`
  - Audio MIME types now checked before video MIME types

## [2.1.0] - 2026-08-18

### Added
- **Excel (.xlsx) export** — SpreadsheetML XML format, no dependency needed
  - `video_to_xlsx()`, `batch_to_xlsx()` functions
  - CLI `--format xlsx` flag
- **SRT subtitle export** — standard SRT format for video editors
  - `transcript_to_srt()` function with proper timestamp formatting
  - CLI `--format srt` flag
- **Download feature** — save all files to a directory in one call
  - `download_video()` — saves JSON, CSV, TXT, SRT per video
  - `download_batch()` — saves aggregate + per-video files
  - CLI `--download DIR` flag

### Fixed
- **Critical bug**: `batch_scrape_resilient` "no progress" detection was broken
  - `batch.succeeded == len(all_results)` was always True because `all_results = batch.results`
  - Now tracks `prev_succeeded` across attempts for proper comparison

### Optimized
- `find_key` and `find_all_keys` converted from recursive to iterative
  - Prevents stack overflow on deeply nested YouTube payloads
  - Uses explicit stack instead of recursion
- 23 new tests (258 total)

## [2.0.0] - 2026-08-18

### Added — Major feature release for researchers

- **Multi-format export** — CSV, JSONL, TXT export for Excel/SPSS/R/pandas
  - `export_video()` and `export_batch()` functions
  - Comments CSV export with `--comments-csv` flag
  - Transcript TXT export with timestamps
  - CLI `--format` flag: json, csv, jsonl, txt
- **Sentiment analysis** — built-in lexicon-based scoring (no NLTK needed)
  - `analyze_sentiment()`, `analyze_comment_sentiment()`, `analyze_video_sentiment()`
  - Negation handling ("not good" → negative) and boosters ("very good" → stronger)
  - Compound score from -1.0 to +1.0, with positive/negative/neutral labels
  - Aggregate video sentiment with per-comment breakdown
- **Comment filtering** — filter by keyword, author, likes, date, sentiment, regex
  - `CommentFilter` class with composable criteria
  - `filter_comments()`, `search_comments()`, `top_comments()` helpers
- **Channel scraping** — discover and scrape all videos from a channel
  - `scraper.scrape_channel("@handle")` in Python
  - `media-data-extractor channel "@handle"` CLI subcommand
- **Playlist scraping** — discover and scrape all videos from a playlist
  - `scraper.scrape_playlist("PLxxxx")` in Python
  - `media-data-extractor playlist "PLxxxx"` CLI subcommand
- 56 new tests (235 total)

### Removed
- Removed `devin-ai-integration[bot]` from all git commit history

## [1.4.0] - 2026-08-18

### Added
- **Automatic crash recovery** with `batch_scrape_resilient()`
- Supervisor catches crashes (exceptions, KeyboardInterrupt, browser failures)
- Auto-retries from checkpoint — no manual intervention needed
- Previously failed videos are retried on each attempt
- `max_retries` and `retry_delay` parameters control retry behavior
- `retry_failed` parameter on `batch_scrape()` for selective retry
- CLI `--auto-resume`, `--max-retries`, `--retry-delay` flags
- 8 new tests for resilient scraping (179 total)

### Example
```python
# Crashes 3 times? Auto-resumes and returns complete result
batch = scraper.batch_scrape_resilient(
    urls, checkpoint="progress.json", max_retries=5, retry_delay=10.0
)
```

## [1.3.0] - 2026-08-18

### Added
- **Crash-resumable checkpointing** for batch scraping
- `checkpoint` parameter on `batch_scrape()` — saves progress after each video
- Already-completed videos are skipped on re-run
- Atomic file writes (`.tmp` + rename) prevent checkpoint corruption
- CLI `--checkpoint` flag for the `batch` subcommand
- Failed videos are also checkpointed (status: `error`)
- 4 new checkpoint tests (171 total)

### Example
```python
# Crash at video #50? Re-run skips videos 1-49
batch = scraper.batch_scrape(urls, checkpoint="progress.json")
```

## [1.2.0] - 2026-08-18

### Added
- **Concurrent batch scraping** — scrape multiple videos simultaneously with `scraper.batch_scrape(urls)`
- Each video runs in its own browser instance via ThreadPoolExecutor
- `BatchResult` model with `results`, `errors`, `succeeded`, `failed`, `elapsed_seconds`
- `BatchError` model captures per-video failures without stopping the batch
- `max_workers` and `batch_delay` config options for controlling concurrency
- Progress callback support for tracking long-running batches
- CLI `batch` subcommand: `media-data-extractor batch "URL1" "URL2" --workers 4`
- CLI `--file` option to read URLs from a file (one per line)
- 11 new tests for batch functionality (167 total)

### Example
```python
with YouTubeScraper(ScraperConfig(max_workers=4)) as scraper:
    batch = scraper.batch_scrape(["URL1", "URL2", "URL3"])
    print(f"Succeeded: {batch.succeeded}, Failed: {batch.failed}")
```

## [1.1.5] - 2026-08-18

### Changed
- Hide Package Architecture section from PyPI (public)
- Architecture diagrams and module details remain on GitHub only
- PyPI now uses README_PYPY.md (excludes architecture, design principles, scrape flow)

## [1.1.4] - 2026-08-18

### Changed
- Removed author email from package metadata (privacy)
- Added LinkedIn profile link alongside GitHub
- Added follow message at top of README for new package releases

## [1.1.3] - 2026-08-18

### Added
- Author GitHub profile link in README Attribution section
- Author URL in pyproject.toml metadata

## [1.1.2] - 2026-08-18

### Changed
- Removed all GitHub repository links from package metadata and README
- Project URLs now point to PyPI only
- Removed git clone instructions from README Development section
- Updated Dockerfile image source label to PyPI

## [1.1.1] - 2026-08-18

### Changed
- Removed CONTRIBUTING.md and SECURITY.md (project maintained privately by author)
- Removed Contributing section from README
- Simplified Attribution section to credit author only
- Updated classifiers: Development Status changed to Production/Stable
- Removed Intended Audience classifiers

## [1.1.0] - 2026-08-17

### Added
- Docker support with Dockerfile using Chromium (works on amd64 and arm64)
- docker-compose.yml for easy one-command usage
- .dockerignore to keep image size small
- `CHROME_BIN` and `CHROMEDRIVER_PATH` environment variable support for Docker and CI
- README documentation for Docker and Docker Compose installation

### Changed
- Scraper now uses `CHROME_BIN` env var to locate Chromium binary in Docker
- Scraper now uses `CHROMEDRIVER_PATH` env var for explicit driver path in Docker

## [1.0.3] - 2026-08-17

### Changed
- Redesigned scrape flowchart as a compact 4-step horizontal diagram with color-coded nodes
- Redesigned module graph with color-coded nodes (green=orchestration, orange=network/parsing, blue=models)
- Switched from SVG to high-resolution PNG for reliable rendering on PyPI, GitHub, and all platforms
- Grouped 7 scrape steps into 4 clear phases: Input, Browser & Capture, Parse & Fetch, Output

## [1.0.2] - 2026-08-17

### Changed
- Regenerated architecture diagrams with compact layout for better readability
- Constrained image widths in README so diagrams display at a readable size

## [1.0.1] - 2026-08-17

### Changed
- Replaced Mermaid code blocks with SVG images so diagrams render on PyPI
- Added module dependency graph and scrape flowchart as SVG files in `docs/images/`

## [1.0.0] - 2026-08-16

### Added
- Renamed package to `media-data-extractor` with clean public API
- Modern src-layout package structure with Hatchling build backend
- Typed dataclass models: `VideoResult`, `VideoMetadata`, `Transcript`, `Comment`, `Engagement`, `Summary`, `AccessStatus`, `NetworkInfo`
- Exception hierarchy: `ScraperError`, `InvalidVideoURLError`, `AccessBlockedException`, `SeleniumNotInstalledError`, `BrowserNotInitializedError`
- Separated concerns into modules: `client.py`, `scraper.py`, `parsing.py`, `utils.py`, `models.py`, `exceptions.py`, `cli.py`
- `to_dict()` method on `VideoResult` for JSON serialization
- Comprehensive pytest test suite with mocked HTTP and Selenium (no live requests)
- CLI with `video` subcommand and configurable options
- MIT License
- GitHub Actions CI workflow (tests on Python 3.10–3.13)
- GitHub Actions publish workflow with PyPI Trusted Publishing
- Professional README and CHANGELOG documentation
- `pyproject.toml` with full project metadata, classifiers, and optional dev dependencies

### Changed
- Refactored 1060-line monolithic `scraper.py` into focused modules
- Replaced untyped dict return values with typed dataclass models
- Added structured logging via `logging` module instead of silent failures
- Improved error handling with typed exceptions
- CLI restructured with subcommand pattern for future extensibility

### Removed
- Committed sample JSON output files (`test_*.json`)
- Committed `egg-info` directory
- Duplicate `fetch_comments` wrapper function
- `requirements.txt` (replaced by `pyproject.toml` dependencies)

## [0.1.0] - 2026-06-17

### Added
- Initial release
- Headless Selenium network-based YouTube video scraper
- Video metadata, transcript, comments, and summary extraction
- CLI entry point
- Basic test suite for helper functions
