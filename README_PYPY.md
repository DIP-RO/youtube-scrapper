# yt-network-scraper

> **Follow for more packages:** I'm actively building Python packages that make development easier — scraping, automation, data tools, and more. Follow me on [GitHub](https://github.com/DIP-RO) and [LinkedIn](https://www.linkedin.com/in/dipro-paul) to stay updated on new releases.

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

### Option 1: pip (requires Chrome installed locally)

```bash
pip install yt-network-scraper
```

**Prerequisites**: Google Chrome must be installed. Selenium Manager will automatically fetch a matching ChromeDriver in recent Selenium versions.

### Option 2: Docker (no Chrome installation needed)

No need to install Chrome, Python, or any dependencies — Docker handles everything:

```bash
# Build the image
docker build -t yt-network-scraper .

# Scrape a video and save output to ./output/result.json
docker run --rm -v "$(pwd)/output:/output" yt-network-scraper \
  video "https://youtu.be/ALyQ-c9_HBI" --comments 25 --pretty --out /output/result.json
```

### Option 3: Docker Compose

```bash
# Build and run with docker compose
docker compose run --rm yt-network-scraper \
  video "https://youtu.be/ALyQ-c9_HBI" --comments 25 --pretty --out /output/result.json
```

The `docker-compose.yml` is included in the repo. Output files are saved to the `./output/` directory via a mounted volume.

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

### Batch Scraping (Multiple Videos Concurrently)

Scrape multiple videos in parallel — each video gets its own browser instance running in a thread pool. Failed videos are captured without stopping the batch:

```python
from yt_network_scraper import YouTubeScraper, ScraperConfig

config = ScraperConfig(
    max_comments=25,
    max_workers=4,       # 4 concurrent Chrome instances
    batch_delay=2.0,     # 2s delay between starting each task
)

with YouTubeScraper(config) as scraper:
    batch = scraper.batch_scrape([
        "https://youtu.be/VIDEO1",
        "https://youtu.be/VIDEO2",
        "https://youtu.be/VIDEO3",
        "VIDEO_ID_4",
    ])

    print(f"Succeeded: {batch.succeeded}, Failed: {batch.failed}")
    print(f"Time: {batch.elapsed_seconds}s")

    for result in batch.results:
        print(f"  {result.video_id}: {result.metadata.title}")

    for err in batch.errors:
        print(f"  FAILED: {err.url_or_id} — {err.error_message}")
```

**With a progress callback** (useful for long batches):

```python
def progress(idx, total, video_id, status):
    print(f"  [{idx}/{total}] {status.upper():5s} — {video_id}")

batch = scraper.batch_scrape(urls, progress_callback=progress)
```

**CLI batch command:**

```bash
# Scrape multiple videos concurrently
yt-network-scraper batch "URL1" "URL2" "URL3" --workers 4 --pretty --out batch.json

# Or read URLs from a file (one per line)
yt-network-scraper batch --file urls.txt --workers 3 --comments 50 --out batch.json
```

### Crash-Resumable Checkpointing

For large batches, use a **checkpoint file** to save progress incrementally. If the process crashes or you stop it, re-running with the same checkpoint file skips already-completed videos:

```python
with YouTubeScraper(config) as scraper:
    batch = scraper.batch_scrape(
        urls,
        checkpoint="batch_progress.json",  # saves after each video
    )
    # If this crashes at video #50, re-running the same command
    # will skip videos 1-49 and resume from #50
```

**CLI with checkpoint:**

```bash
# First run — crashes or is interrupted
yt-network-scraper batch --file urls.txt --workers 4 --checkpoint progress.json --out batch.json

# Re-run — skips completed videos automatically
yt-network-scraper batch --file urls.txt --workers 4 --checkpoint progress.json --out batch.json
```

The checkpoint file is a JSON file that records each video's status (`ok` or `error`) and result data. It's written atomically after each video completes, so progress is never lost.

### Auto-Resume (Automatic Crash Recovery)

For production workloads, use `batch_scrape_resilient` to automatically recover from any crash — browser failures, network errors, even Ctrl+C. The supervisor catches the crash, waits, and retries from the checkpoint. Previously failed videos are retried. The user never sees an unhandled error:

```python
with YouTubeScraper(config) as scraper:
    batch = scraper.batch_scrape_resilient(
        urls,
        checkpoint="progress.json",
        max_retries=5,       # retry up to 5 times
        retry_delay=10.0,    # wait 10s between retries
    )
    # Even if the process crashes 3 times, it auto-resumes
    # and returns the complete result.
    print(f"Done: {batch.succeeded} ok, {batch.failed} failed")
```

**How it works:**

```
Attempt 1: Scrape 100 videos → videos 1-50 succeed → CRASH at #51
    ↓ (auto-caught, wait 10s)
Attempt 2: Skip 1-50 (checkpoint) → retry #51-100 → #51-80 succeed → CRASH at #81
    ↓ (auto-caught, wait 10s)
Attempt 3: Skip 1-80 → retry #81-100 → all succeed → DONE
    ↓
Return BatchResult (100 succeeded, 0 failed)
```

**CLI with auto-resume:**

```bash
# Automatically retries on any crash — no manual intervention needed
yt-network-scraper batch --file urls.txt --workers 4 \
    --checkpoint progress.json \
    --auto-resume \
    --max-retries 5 \
    --retry-delay 10 \
    --out batch.json
```

### Channel & Playlist Scraping

Scrape all videos from a YouTube channel or playlist in one command. The scraper discovers video IDs from the channel/playlist page, then batch scrapes them concurrently:

```python
with YouTubeScraper(config) as scraper:
    # Scrape up to 50 videos from a channel
    batch = scraper.scrape_channel("@handle", max_videos=50)

    # Scrape all videos from a playlist
    batch = scraper.scrape_playlist("PLxxxx", max_videos=100)

    print(f"Scraped {batch.succeeded} videos from {batch.total} discovered")
```

**CLI:**

```bash
# Scrape all videos from a channel
yt-network-scraper channel "@mkbhd" --max-videos 50 --workers 4 --out channel.json

# Scrape all videos from a playlist
yt-network-scraper playlist "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf" --workers 4 --out playlist.json

# With crash recovery
yt-network-scraper channel "@handle" --auto-resume --checkpoint progress.json --out channel.json
```

### Multi-Format Export (CSV, JSONL, TXT)

Export scraped data to formats commonly used by researchers and data analysts:

```python
from yt_network_scraper import export_video, export_batch

# Single video
csv_data = export_video(result, format="csv")           # metadata CSV
comments_csv = export_video(result, format="csv", comments=True)  # comments CSV
txt_data = export_video(result, format="txt")           # transcript TXT
jsonl_data = export_video(result, format="jsonl")       # JSONL (one line)

# Batch
batch_csv = export_batch(batch, format="csv")           # one row per video
batch_comments_csv = export_batch(batch, format="csv", comments=True)  # all comments
batch_jsonl = export_batch(batch, format="jsonl")       # one JSON per line
```

**CLI:**

```bash
# Export to CSV
yt-network-scraper video "URL" --format csv --out result.csv

# Export comments to CSV
yt-network-scraper video "URL" --format csv --comments-csv --out comments.csv

# Export transcript to TXT
yt-network-scraper video "URL" --format txt --out transcript.txt

# Export batch to CSV
yt-network-scraper batch --file urls.txt --format csv --out batch.csv

# Export all comments from batch to CSV
yt-network-scraper batch --file urls.txt --format csv --comments-csv --out all_comments.csv
```

### Sentiment Analysis

Built-in lexicon-based sentiment scoring for comments — no external dependencies (NLTK, transformers) required:

```python
from yt_network_scraper import analyze_sentiment, analyze_video_sentiment

# Analyze a single text
result = analyze_sentiment("This video is amazing and very helpful!")
print(result.label)       # "positive"
print(result.compound)    # 0.85

# Analyze all comments in a video
sentiment = analyze_video_sentiment(video_result)
print(sentiment.overall_label)      # "positive"
print(sentiment.positive_count)     # 15
print(sentiment.negative_count)     # 3
print(sentiment.neutral_count)      # 7
print(sentiment.average_compound)   # 0.42

# Per-comment breakdown
for cs in sentiment.comment_sentiments:
    print(f"  {cs.comment.author}: {cs.sentiment.label} ({cs.sentiment.compound:.2f})")
```

The sentiment scorer uses a curated lexicon of positive/negative words with negation handling ("not good" → negative) and booster amplification ("very good" → more positive). Scores range from -1.0 (very negative) to +1.0 (very positive).

### Comment Filtering

Filter comments by keyword, author, likes, date range, sentiment, or regex:

```python
from yt_network_scraper import filter_comments, search_comments, top_comments, CommentFilter

# Filter by keyword
filtered = filter_comments(result, keyword="python")

# Filter by author
filtered = filter_comments(result, author="john")

# Filter by likes range
filtered = filter_comments(result, min_likes=10, max_likes=100)

# Filter by sentiment
filtered = filter_comments(result, sentiment="positive")

# Filter by regex
filtered = filter_comments(result, regex=r"python|tutorial")

# Combined filters
filtered = filter_comments(result, keyword="great", min_likes=5, sentiment="positive")

# Quick search
results = search_comments(result, "tutorial")

# Top comments by likes
top = top_comments(result, n=10)
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

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Attribution

Developed and maintained by **Dipro Paul**.

- **GitHub:** [github.com/DIP-RO](https://github.com/DIP-RO)
- **LinkedIn:** [linkedin.com/in/dipro-paul](https://www.linkedin.com/in/dipro-paul)

I release Python packages that make development easier — scraping, automation, data tools, and more. Follow for new releases.

## Disclaimer

This package is intended for **legitimate research, data analysis, and automation of publicly available YouTube video data**. Users are responsible for complying with:

- YouTube's Terms of Service
- Applicable local and international laws
- Rate limiting and access restrictions

This package does **not** bypass CAPTCHAs, evade bot detection, circumvent authentication, or harvest credentials. If YouTube returns an access challenge, the scraper reports it rather than attempting to work around it. Use responsibly and at your own risk.
