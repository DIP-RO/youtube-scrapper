# yt-network-scraper

A network-first YouTube video scraper that extracts metadata, transcripts, comments, and summaries from captured network payloads using headless Chrome and Selenium.

Unlike traditional DOM scrapers, this package opens a real browser via Selenium, captures network responses through Chrome DevTools performance logs, and parses YouTube's own JSON payloads (`ytInitialPlayerResponse`, `ytInitialData`, `ytcfg`). It then uses YouTube's innertube API for transcripts and comments. This approach is more resilient to UI changes and avoids brittle CSS selectors.

## Why yt-network-scraper?

There are several excellent YouTube libraries on PyPI. Here is how `yt-network-scraper` compares to the most popular ones, so you can pick the right tool for your use case:

| Feature | yt-network-scraper | yt-dlp | pytube / pytubefix | youtube-transcript-api | ytscrape | tubescrape |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Video metadata** | Yes | Yes | Yes | No | Yes | Yes |
| **Transcript / captions** | Yes | Yes | No | Yes | Yes | Yes |
| **Comments** | Yes | No | No | No | Yes | No |
| **Dislike counts** | Yes (RYD API) | No | No | No | No | No |
| **Extractive summary** | Yes | No | No | No | No | No |
| **Access-block detection** | Yes | No | No | No | No | No |
| **Typed dataclass models** | Yes | No | No | Yes | Yes | Yes |
| **JSON serialization** | Yes (`to_dict()`) | No | No | No | No | Yes |
| **CLI** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Search videos** | No | Limited | No | No | Yes | Yes |
| **Channel browsing** | No | Yes | No | No | Yes | Yes |
| **Playlists** | No | Yes | Yes | No | No | Yes |
| **Video download** | No | Yes | Yes | No | No | No |
| **Async support** | No | No | No | No | Yes | Yes |
| **Approach** | Browser + network capture | HTTP | HTTP | HTTP | HTTP (innertube) | HTTP (innertube) |
| **Browser required** | Yes (Chrome) | No | No | No | No | No |
| **API key needed** | No | No | No | No | No | No |
| **Core dependencies** | selenium, requests | many | 0 | requests | requests, pycountry | httpx |
| **Python** | 3.10+ | 3.10+ | 3.7+ | 3.9+ | 3.10+ | 3.10+ |
| **License** | MIT | Unlicense | Unlicense | MIT | MIT | MIT |

### When to use yt-network-scraper

**Use this package if you need:**

- **Comments** — very few libraries extract YouTube comments. This one does, with full author info, likes, hearted/pinned status, and reply counts.
- **Dislike counts** — integrated with the Return YouTube Dislike API, which no other listed library provides.
- **Automatic summaries** — built-in extractive summarization of transcripts, so you get a quick text summary alongside the full transcript.
- **Access-block detection** — detects CAPTCHAs, consent walls, and sign-in challenges and reports them rather than silently failing or trying to bypass them.
- **A real browser session** — some videos require JavaScript rendering and network-level payload capture that pure HTTP libraries cannot access. This package captures Chrome DevTools performance logs to extract YouTube's own JSON payloads.
- **A single, unified result object** — metadata, transcript, comments, engagement, summary, and network diagnostics in one typed `VideoResult` with `to_dict()` for JSON serialization.

**Use a different package if you need:**

- **Video downloading** → use `yt-dlp` or `pytube`
- **Search or channel browsing** → use `ytscrape` or `tubescrape`
- **Transcripts only (lightweight, no browser)** → use `youtube-transcript-api`
- **Async / high-throughput scraping** → use `ytscrape` or `tubescrape`
- **Playlist extraction** → use `yt-dlp`, `pytube`, or `tubescrape`

## Features

- **Video metadata**: title, description, views, channel info, publish/upload dates, duration, tags, thumbnail
- **Transcripts / captions**: via timedtext URLs or the innertube `get_panel` endpoint, with automatic fallback
- **Comments**: via the innertube `next` continuation API, with deduplication and pagination
- **Dislike counts**: from the [Return YouTube Dislike](https://returnyoutubedislike.com) API
- **Extractive summaries**: word-frequency-based summarization of transcript or description text
- **Access-block detection**: detects CAPTCHAs, consent walls, and sign-in challenges (does **not** bypass them)
- **Structured data models**: typed dataclasses with JSON serialization
- **CLI**: convenient command-line interface
- **Configurable**: timeout, retries, delays, comment limits, language preference

## Installation

```bash
pip install yt-network-scraper
```

**Prerequisites**: Google Chrome must be installed. Selenium Manager will automatically fetch a matching ChromeDriver in recent Selenium versions.

## Quick Start

```python
from yt_network_scraper import YouTubeScraper, ScraperConfig

config = ScraperConfig(max_comments=50, transcript_language="en")

with YouTubeScraper(config) as scraper:
    result = scraper.get_video("dQw4w9WgXcQ")

    print(result.metadata.title)
    print(f"Views: {result.metadata.views}")
    print(f"Channel: {result.metadata.channel_name}")

    if result.transcript.available:
        print(f"Transcript: {result.transcript.text[:200]}")

    if result.summary.available:
        print(f"Summary: {result.summary.text}")

    for comment in result.comments:
        print(f"  {comment.author}: {comment.text}")
```

You can pass a full URL, a youtu.be link, a shorts URL, or a bare 11-character video ID:

```python
scraper.get_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
scraper.get_video("https://youtu.be/dQw4w9WgXcQ")
scraper.get_video("https://www.youtube.com/shorts/dQw4w9WgXcQ")
scraper.get_video("dQw4w9WgXcQ")
```

## Sample Response

Here is an example of the actual JSON output you get when scraping a real video. This was produced by running:

```bash
yt-network-scraper video "https://youtu.be/ALyQ-c9_HBI" --comments 5 --pretty
```

The result is a `VideoResult` object. Calling `result.to_dict()` (or using `--pretty` / `--out` in the CLI) produces JSON with this structure:

```json
{
  "video_id": "ALyQ-c9_HBI",
  "source_url": "https://www.youtube.com/watch?v=ALyQ-c9_HBI&hl=en&persist_hl=1",
  "metadata": {
    "video_url": "https://www.youtube.com/watch?v=ALyQ-c9_HBI",
    "title": "এটিএন বাংলার সন্ধ্যা ৭ টার সংবাদ । 16.08.2026 | Today News ...",
    "description": "#atn #atnbangla #atnbanglanews ... Fair Usage Policy: ...",
    "views": 64649,
    "channel_name": "ATN Bangla News",
    "channel_id": "UCbgcYEdMsuypG2NJ-znBp3w",
    "channel_url": "http://www.youtube.com/@ATNBanglanews",
    "channel_subscribers": "10.3M subscribers",
    "upload_date": "2026-08-16T07:45:34-07:00",
    "publish_date": "2026-08-16T07:45:34-07:00",
    "duration_seconds": 2028,
    "category": "News & Politics",
    "is_live": false,
    "keywords": ["atn bangla news", "atnbangla", "bangla news", ...],
    "thumbnail": "https://i.ytimg.com/vi/ALyQ-c9_HBI/maxresdefault.jpg"
  },
  "engagement": {
    "comment_count_scraped": 5,
    "likes": 652,
    "views": 64649,
    "dislikes": {
      "source": "returnyoutubedislikeapi.com",
      "dislikes": 10,
      "likes": 648,
      "rating": 4.94,
      "view_count": 63292
    },
    "comment_count": 8
  },
  "transcript": {
    "available": true,
    "segments": [
      {
        "text": "আসসালামু আলাইকুম। এটিএন বাংলা সংবাদে সবাইকে স্বাগত ...",
        "start_ms": 8000,
        "duration_ms": null,
        "time": "0:08"
      },
      {
        "text": "রাজপথে বিশৃঙ্খলা সৃষ্টিকারীদের রুখে দেওয়ার আহ্বান ...",
        "start_ms": 16000,
        "time": "0:16"
      }
    ],
    "text": "আসসালামু আলাইকুম। এটিএন বাংলা সংবাদে সবাইকে স্বাগত ...",
    "language": "bn",
    "name": "Bangla (auto-generated)",
    "is_auto_generated": true,
    "source": "browser_network_get_panel"
  },
  "summary": {
    "available": true,
    "text": "আসসালামু আলাইকুম। এটিএন বাংলা সংবাদে সবাইকে স্বাগত ...",
    "method": "lead_sentences"
  },
  "comments": [
    {
      "comment_id": "Ugxxd7ztzYUkFIlchVl4AaABAg",
      "likes": 5,
      "reply_count": 0,
      "is_pinned": false,
      "is_hearted": true,
      "author": "@MdHoksap",
      "author_channel_id": "UC5DBcRWdv8oCmPhIauoy3gw",
      "author_channel_url": "/@MdHoksap",
      "text": "তারেক রহমান চাঁন্দাবাজের জন্য অপযোগী ...",
      "published": "3 hours ago"
    },
    {
      "comment_id": "UgzgNUoDsKC25nuDmhp4AaABAg",
      "likes": 0,
      "reply_count": 0,
      "is_pinned": false,
      "is_hearted": true,
      "author": "@MinhajUddin-s8n",
      "text": "SALARY OF ALL GOVT WORKERS IN SENIOR RANK MUST BE REDUCED ...",
      "published": "1 hour ago"
    }
  ],
  "network": {
    "access_status": {
      "blocked": false,
      "reasons": [],
      "message": "Access looks normal"
    },
    "api_key_found": true,
    "captured_event_count": 2256,
    "dom_scraping": false,
    "bot_evasion": false
  }
}
```

### What each field contains

| Field | Description |
|-------|-------------|
| `video_id` | The 11-character YouTube video ID |
| `source_url` | The exact watch URL that was loaded |
| `metadata.title` | Video title |
| `metadata.description` | Full video description (may be long) |
| `metadata.views` | View count as an integer |
| `metadata.channel_name` | Channel display name |
| `metadata.channel_id` | YouTube channel ID (`UC...`) |
| `metadata.channel_url` | Channel profile URL |
| `metadata.channel_subscribers` | Subscriber count text (e.g. `"10.3M subscribers"`) |
| `metadata.upload_date` | ISO 8601 upload timestamp |
| `metadata.publish_date` | ISO 8601 publish timestamp |
| `metadata.duration_seconds` | Video length in seconds |
| `metadata.category` | YouTube category (e.g. `"News & Politics"`) |
| `metadata.keywords` | List of video tags/keywords |
| `metadata.thumbnail` | Highest-resolution thumbnail URL |
| `engagement.likes` | Like count (from metadata or RYD API) |
| `engagement.views` | View count |
| `engagement.dislikes` | Dislike data from Return YouTube Dislike API (may be `null`) |
| `engagement.comment_count` | Total comment count reported by YouTube |
| `engagement.comment_count_scraped` | Number of comments actually fetched |
| `transcript.available` | Whether a transcript was found |
| `transcript.segments` | List of timed `{text, start_ms, duration_ms, time}` segments |
| `transcript.text` | Full transcript as a single string |
| `transcript.language` | ISO language code (e.g. `"en"`, `"bn"`) |
| `transcript.is_auto_generated` | Whether captions are auto-generated (ASR) |
| `transcript.source` | How the transcript was fetched (`"timedtext"` or `"browser_network_get_panel"`) |
| `summary.available` | Whether a summary was generated |
| `summary.text` | The summary text |
| `summary.method` | Summarization method (`"short_text_passthrough"`, `"frequency_extractive"`, `"lead_sentences"`, or `"none"`) |
| `comments` | List of comment objects with `author`, `text`, `likes`, `published`, `is_hearted`, `is_pinned` |
| `network.access_status.blocked` | Whether YouTube returned an access challenge |
| `network.access_status.reasons` | List of block reasons (e.g. `["captcha", "unusual_traffic"]`) |
| `network.api_key_found` | Whether the innertube API key was extracted |
| `network.captured_event_count` | Number of network events captured by Chrome DevTools |
| `network.dom_scraping` | Always `false` — this scraper does not scrape the DOM |
| `network.bot_evasion` | Always `false` — this scraper does not evade bot detection |

## API Usage

### `YouTubeScraper`

The main scraper class. Must be used as a context manager to manage the browser lifecycle.

```python
from yt_network_scraper import YouTubeScraper, ScraperConfig

config = ScraperConfig(
    headless=True,           # Run Chrome in headless mode
    timeout=25,              # Browser page-load timeout (seconds)
    max_comments=25,         # Maximum comments to fetch
    transcript_language="en", # Preferred transcript language
    request_delay=1.5,       # Delay between fallback requests (seconds)
    max_page_retries=2,      # Retries on access-block pages
)

with YouTubeScraper(config) as scraper:
    result = scraper.get_video("VIDEO_ID")
```

### `VideoResult`

The return type of `get_video()`. Contains:

| Field | Type | Description |
|-------|------|-------------|
| `video_id` | `str` | The 11-character YouTube video ID |
| `source_url` | `str` | The watch URL that was scraped |
| `metadata` | `VideoMetadata` | Title, description, views, channel info, dates, etc. |
| `engagement` | `Engagement` | Likes, views, dislikes, comment counts |
| `transcript` | `Transcript` | Transcript segments and full text |
| `summary` | `Summary` | Extractive summary |
| `comments` | `list[Comment]` | Scraped comments |
| `network` | `NetworkInfo` | Diagnostic info about the scraping process |

Call `result.to_dict()` to serialize the entire result to a JSON-compatible dictionary.

### Exceptions

```python
from yt_network_scraper import (
    ScraperError,              # Base exception
    InvalidVideoURLError,      # URL/ID could not be parsed
    AccessBlockedException,    # YouTube returned an access challenge
    SeleniumNotInstalledError, # Selenium is not installed
    BrowserNotInitializedError, # Not used as a context manager
)
```

## CLI Usage

```bash
# Scrape a video and print JSON to stdout
yt-network-scraper video "https://www.youtube.com/watch?v=VIDEO_ID"

# Save to a file with pretty-printing
yt-network-scraper video VIDEO_ID --out result.json --pretty

# Fetch up to 100 comments in French
yt-network-scraper video VIDEO_ID --comments 100 --lang fr

# Show Chrome (for debugging)
yt-network-scraper video VIDEO_ID --no-headless

# Custom timeout and retries
yt-network-scraper video VIDEO_ID --timeout 60 --retries 5
```

## Configuration

All configuration is done through the `ScraperConfig` dataclass:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `headless` | `True` | Run Chrome in headless mode |
| `timeout` | `25` | Browser page-load timeout in seconds |
| `max_comments` | `25` | Maximum number of comments to fetch |
| `transcript_language` | `"en"` | Preferred ISO language code for transcripts |
| `request_delay` | `1.5` | Base delay between fallback network requests (seconds) |
| `max_page_retries` | `2` | Number of retries when YouTube returns a block page |
| `user_agent` | Chrome 125 UA | User-Agent string for the browser and HTTP session |

## Package Architecture

The package is organized into focused, single-responsibility modules under `src/yt_network_scraper/`. This separation of concerns makes the codebase easy to test, maintain, and extend:

<img src="https://raw.githubusercontent.com/DIP-RO/youtube-scrapper/main/docs/images/module-graph.svg" alt="Module dependency graph" width="100%" />

| Module | Responsibility |
|--------|---------------|
| `__init__.py` | Public API exports — `YouTubeScraper`, `ScraperConfig`, all models, all exceptions |
| `client.py` | HTTP/network layer — Selenium browser lifecycle, Chrome DevTools log capture, innertube API calls, Return YouTube Dislike API integration |
| `scraper.py` | Orchestration layer — coordinates the full scrape workflow: load page → capture network → parse metadata → fetch transcript → fetch comments → fetch dislikes → generate summary → build `VideoResult` |
| `parsing.py` | Pure parsing functions — extracts metadata, transcript, comments, and access-block status from YouTube JSON payloads. No network calls. |
| `models.py` | Typed dataclass models — `VideoResult`, `VideoMetadata`, `Transcript`, `TranscriptSegment`, `Comment`, `Engagement`, `DislikeData`, `Summary`, `AccessStatus`, `NetworkInfo`. Each has `to_dict()` for JSON serialization. |
| `exceptions.py` | Exception hierarchy — `ScraperError` (base), `InvalidVideoURLError`, `AccessBlockedException`, `SeleniumNotInstalledError`, `BrowserNotInitializedError`, `TranscriptUnavailableError` |
| `utils.py` | Utilities — URL validation, video ID extraction, text summarization, sentence splitting, key lookup helpers, HTML unescaping |
| `cli.py` | Command-line interface — argparse-based CLI with `video` subcommand |

### How a scrape works

<img src="https://raw.githubusercontent.com/DIP-RO/youtube-scrapper/main/docs/images/scrape-flow.svg" alt="Scrape flowchart" width="100%" />

### Design principles

- **Network layer is isolated** — all Selenium and HTTP calls live in `client.py`. Parsing functions in `parsing.py` are pure and take dicts as input, making them trivial to test with fixtures.
- **Typed models everywhere** — the scraper never returns raw dicts. Every result is a typed dataclass with documented fields, optional fields are `None` when unavailable, and `to_dict()` produces clean JSON.
- **Defensive parsing** — YouTube changes payload shapes frequently. Every parser uses safe key lookups (`find_key`, `find_all_keys`) and returns `None` or empty lists for missing fields instead of raising exceptions.
- **No bot evasion** — the scraper detects access blocks but never tries to bypass them. If YouTube returns a CAPTCHA or consent wall, the `network.access_status` field reports it and the scrape completes with available data.
- **Configurable behavior** — `ScraperConfig` controls headless mode, timeout, retries, delays, comment limits, transcript language, and user agent. Sensible defaults work for most cases.

## Error Handling

The scraper uses a typed exception hierarchy. All exceptions inherit from `ScraperError`:

```python
from yt_network_scraper import YouTubeScraper, ScraperError

try:
    with YouTubeScraper() as scraper:
        result = scraper.get_video("bad_url")
except ScraperError as e:
    print(f"Scraping failed: {e}")
```

The scraper is designed to be **defensive** — YouTube frequently changes internal payload shapes. Missing fields are returned as `None` or empty lists rather than raising exceptions. The `network.access_status` field in the result indicates whether YouTube returned an access challenge.

## Development

```bash
# Clone the repository
git clone https://github.com/DIP-RO/yt-network-scraper.git
cd yt-network-scraper

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=yt_network_scraper

# Build the package
python -m build

# Validate the build
twine check dist/*
```

## Running Tests

```bash
pytest
```

The test suite uses mocked HTTP responses and mocked Selenium drivers — no live YouTube requests or browser instances are required. Tests cover:

- Package imports and public API surface
- Data model serialization
- URL parsing and ID extraction
- YouTube payload parsing (metadata, transcripts, comments)
- Network fetching with mocked sessions (success, errors, edge cases)
- Client orchestration with mocked Selenium
- CLI argument parsing and output

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Attribution

This package was originally developed by Dipro Paul as a network-first YouTube scraper. The core scraping logic, parsing functions, and network-capture approach were preserved and reorganized into a clean, modular package structure with typed data models, comprehensive tests, and proper open-source packaging.

## Disclaimer

This package is intended for **legitimate research, data analysis, and automation of publicly available YouTube video data**. Users are responsible for complying with:

- YouTube's Terms of Service
- Applicable local and international laws
- Rate limiting and access restrictions

This package does **not** bypass CAPTCHAs, evade bot detection, circumvent authentication, or harvest credentials. If YouTube returns an access challenge, the scraper reports it rather than attempting to work around it. Use responsibly and at your own risk.
