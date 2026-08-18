# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Renamed package to `yt-network-scraper` with clean public API
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
