# media-data-extractor

> **Follow for more packages:** I'm actively building Python packages that make development easier — scraping, automation, data tools, and more. Follow me on [GitHub](https://github.com/DIP-RO) and [LinkedIn](https://www.linkedin.com/in/dipro-paul) to stay updated on new releases.

**Extract metadata, transcripts, comments, sentiment, and video files from YouTube. Includes a built-in video player, playlist manager, and end-to-end research pipeline.**

[![PyPI version](https://img.shields.io/pypi/v/media-data-extractor.svg)](https://pypi.org/project/media-data-extractor/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/media-data-extractor.svg)](https://pypi.org/project/media-data-extractor/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-467%20passing-brightgreen.svg)](#)

A network-first YouTube data extraction toolkit that captures network responses through Chrome DevTools and parses YouTube's own JSON payloads. Unlike traditional DOM scrapers, this package opens a real browser via Selenium, captures network responses, and parses `ytInitialPlayerResponse`, `ytInitialData`, and `ytcfg`. It then uses YouTube's innertube API for transcripts and comments.

**Search keywords:** youtube scraper, youtube data extractor, youtube transcript, youtube comments, youtube metadata, youtube downloader, youtube sentiment analysis, youtube api python, youtube research tool, media data extraction, video scraper python, youtube playlist scraper, youtube channel scraper, youtube batch scraper

## Why media-data-extractor?

There are several excellent YouTube libraries on PyPI. Here is how `media-data-extractor` compares to the most popular ones, so you can pick the right tool for your use case:

| Feature | media-data-extractor | yt-dlp | pytube / pytubefix | youtube-transcript-api | ytscrape | tubescrape |
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

### When to use media-data-extractor

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
pip install media-data-extractor
```

**Prerequisites**: Google Chrome must be installed. Selenium Manager will automatically fetch a matching ChromeDriver in recent Selenium versions.

### Lightweight install options

```bash
# Core scraping only (lightest)
pip install media-data-extractor

# With pandas integration for research datasets
pip install media-data-extractor[research]

# With dev tools (pytest, build, twine)
pip install media-data-extractor[dev]
```

### Lightweight import — only loads what you use

The package uses **lazy imports** — `import media_data_extractor` loads only
core modules (models, exceptions, client). Heavy modules (player, pipeline,
research, downloader, sentiment, filters, performance) load on first access.

For the absolute lightest import path, use the `core` module:

```python
# Lightest import — only scraping, no optional modules
from media_data_extractor.core import YouTubeScraper, ScraperConfig

with YouTubeScraper() as scraper:
    result = scraper.get_video("VIDEO_ID")
```

This loads only 7 modules instead of 16, and never imports selenium until
`__enter__()` is called.

### Option 2: Docker (no Chrome installation needed)

No need to install Chrome, Python, or any dependencies — Docker handles everything:

```bash
# Build the image
docker build -t media-data-extractor .

# Scrape a video and save output to ./output/result.json
docker run --rm -v "$(pwd)/output:/output" media-data-extractor \
  video "https://youtu.be/ALyQ-c9_HBI" --comments 25 --pretty --out /output/result.json
```

### Option 3: Docker Compose

```bash
# Build and run with docker compose
docker compose run --rm media-data-extractor \
  video "https://youtu.be/ALyQ-c9_HBI" --comments 25 --pretty --out /output/result.json
```

The `docker-compose.yml` is included in the repo. Output files are saved to the `./output/` directory via a mounted volume.

### CLI shortcuts

The package installs two CLI commands — they are identical, use whichever is shorter:

```bash
media-data-extractor video "URL"     # full name
mdx video "URL"                       # short alias
```

## Quick Start

```python
from media_data_extractor import YouTubeScraper, ScraperConfig

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
from media_data_extractor import YouTubeScraper, ScraperConfig

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
media-data-extractor batch "URL1" "URL2" "URL3" --workers 4 --pretty --out batch.json

# Or read URLs from a file (one per line)
media-data-extractor batch --file urls.txt --workers 3 --comments 50 --out batch.json
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
media-data-extractor batch --file urls.txt --workers 4 --checkpoint progress.json --out batch.json

# Re-run — skips completed videos automatically
media-data-extractor batch --file urls.txt --workers 4 --checkpoint progress.json --out batch.json
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
media-data-extractor batch --file urls.txt --workers 4 \
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
media-data-extractor channel "@mkbhd" --max-videos 50 --workers 4 --out channel.json

# Scrape all videos from a playlist
media-data-extractor playlist "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf" --workers 4 --out playlist.json

# With crash recovery
media-data-extractor channel "@handle" --auto-resume --checkpoint progress.json --out channel.json
```

### Multi-Format Export (CSV, JSONL, TXT)

Export scraped data to formats commonly used by researchers and data analysts:

```python
from media_data_extractor import export_video, export_batch

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
media-data-extractor video "URL" --format csv --out result.csv

# Export comments to CSV
media-data-extractor video "URL" --format csv --comments-csv --out comments.csv

# Export transcript to TXT
media-data-extractor video "URL" --format txt --out transcript.txt

# Export batch to CSV
media-data-extractor batch --file urls.txt --format csv --out batch.csv

# Export all comments from batch to CSV
media-data-extractor batch --file urls.txt --format csv --comments-csv --out all_comments.csv
```

### Sentiment Analysis

Built-in lexicon-based sentiment scoring for comments — no external dependencies (NLTK, transformers) required:

```python
from media_data_extractor import analyze_sentiment, analyze_video_sentiment

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
from media_data_extractor import filter_comments, search_comments, top_comments, CommentFilter

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

### Excel (.xlsx) Export

Export to Excel XML SpreadsheetML format — no external dependency needed, Excel opens it natively:

```python
from media_data_extractor import export_video, export_batch

# Single video to Excel
xlsx_data = export_video(result, format="xlsx")

# Comments to Excel
xlsx_comments = export_video(result, format="xlsx", comments=True)

# Batch to Excel
xlsx_batch = export_batch(batch, format="xlsx")
```

**CLI:**

```bash
media-data-extractor video "URL" --format xlsx --out result.xlsx
media-data-extractor batch --file urls.txt --format xlsx --out batch.xlsx
```

### SRT Subtitle Export

Export transcripts as SRT subtitle files for use in video editors, media players, and NLP pipelines:

```python
from media_data_extractor import export_video

srt_data = export_video(result, format="srt")
# Output:
# 1
# 00:00:00,000 --> 00:00:02,000
# Hello world
#
# 2
# 00:00:02,000 --> 00:00:05,000
# Second line
```

**CLI:**

```bash
media-data-extractor video "URL" --format srt --out transcript.srt
```

### Download Feature (Save All Files to Directory)

The download feature saves all result files to a directory in one call — perfect for building datasets:

```python
from media_data_extractor import download_video, download_batch

# Save all files for a single video
files = download_video(result, output_dir="./output")
# Creates:
#   output/vid1_result.json
#   output/vid1_metadata.csv
#   output/vid1_comments.csv
#   output/vid1_transcript.txt
#   output/vid1_transcript.srt

# Save all files for a batch
files = download_batch(batch, output_dir="./dataset")
# Creates:
#   dataset/batch_result.json
#   dataset/batch_summary.csv
#   dataset/batch_all_comments.csv
#   dataset/vid1_result.json
#   dataset/vid1_metadata.csv
#   dataset/vid1_comments.csv
#   dataset/vid1_transcript.txt
#   dataset/vid1_transcript.srt
#   ... (per video)

# Choose specific formats
files = download_video(result, "./output", formats=["json", "csv"])
```

**CLI:**

```bash
# Download all files for a single video
media-data-extractor video "URL" --download ./output

# Download all files for a batch
media-data-extractor batch --file urls.txt --workers 4 --download ./dataset

# Download channel data
media-data-extractor channel "@handle" --max-videos 50 --workers 4 --download ./channel_data
```

### Video File Download

Download actual YouTube video files to disk. The scraper extracts stream URLs from YouTube's `streamingData` payload and downloads the video file. For high-quality adaptive formats (1080p+), audio and video are downloaded separately and merged with ffmpeg if available.

```python
from media_data_extractor import YouTubeScraper, ScraperConfig

with YouTubeScraper() as scraper:
    # Download best quality (auto-merges with ffmpeg if needed)
    result = scraper.download_video_file(
        "https://www.youtube.com/watch?v=VIDEO_ID",
        output_path="./video.mp4",
        quality="best",
    )
    if result.success:
        print(f"Downloaded {result.file_size_bytes} bytes to {result.output_path}")
        print(f"Merged: {result.merged}")

    # Download specific quality
    result = scraper.download_video_file(
        "VIDEO_ID",
        output_path="./output/",
        quality="720p",
    )

    # Download audio only
    result = scraper.download_video_file(
        "VIDEO_ID",
        output_path="./audio.m4a",
        quality="audio",
    )

    # List available formats without downloading
    formats = scraper.get_streams("VIDEO_ID")
    for f in formats:
        print(f"  {f.itag} {f.quality_label or f.quality} {f.mime_type}")
```

**CLI:**

```bash
# Download best quality
media-data-extractor download "https://www.youtube.com/watch?v=VIDEO_ID" -o video.mp4

# Download specific quality
media-data-extractor download "VIDEO_ID" -o video.mp4 --quality 720p

# Download audio only
media-data-extractor download "VIDEO_ID" -o audio.m4a --quality audio

# List available formats without downloading
media-data-extractor download "VIDEO_ID" --list-formats
```

**Output of `--list-formats`:**
```
Available formats for VIDEO_ID:
  ITAG  TYPE          QUALITY         SIZE  NOTE
----------------------------------------------------------------------
    18  audio+video   360p        976.6 KB  progressive
    22  audio+video   720p          4.8 MB  progressive
   137  video         1080p        47.7 MB  DASH video
   136  video         720p         19.1 MB  DASH video
   140  audio         medium        1.9 MB  DASH audio
   139  audio         low         488.3 KB  DASH audio
```

**Quality options:**

| Quality | Description |
|---------|-------------|
| `best` | Best available quality (merges with ffmpeg if needed) |
| `worst` | Lowest quality progressive stream |
| `720p` | Specific resolution (falls back to video-only if no progressive) |
| `1080p` | 1080p (requires ffmpeg for audio merge) |
| `4k` | 4K/2160p (requires ffmpeg for audio merge) |
| `audio` | Audio only (m4a or webm) |

**ffmpeg note:** For 1080p and higher, YouTube serves video and audio as separate streams. The downloader automatically merges them if ffmpeg is installed. Without ffmpeg, the video and audio files are saved separately.

Install ffmpeg:
- macOS: `brew install ffmpeg`
- Ubuntu: `sudo apt install ffmpeg`
- Windows: Download from https://ffmpeg.org/download.html

### Video Player (MX Player-style)

Play downloaded videos with playlist support, shuffle, loop, and subtitle loading. Uses ffplay (ffmpeg), VLC, mpv, or the system default player:

```python
from media_data_extractor import VideoPlayer, Playlist, Track, create_playlist_from_directory

# Play a single file
player = VideoPlayer(volume=80)
player.play_file("video.mp4")
player.wait()

# Create and play a playlist
playlist = Playlist(name="My Mix")
playlist.add_track(Track(path="video1.mp4", title="Video 1"))
playlist.add_track(Track(path="video2.mp4", title="Video 2"))
playlist.loop_mode = "all"  # "none", "one", or "all"
playlist.shuffle()

player = VideoPlayer()
player.play_playlist(playlist)
player.play_all()  # Play through entire playlist

# Controls
player.pause()
player.resume()
player.stop()
player.play_next()
player.play_previous()
player.set_volume(50)

# Create playlist from a directory of video files
playlist = create_playlist_from_directory("./downloads")

# Save/load playlists
from media_data_extractor import save_playlist, load_playlist
save_playlist(playlist, "my_playlist.json")
loaded = load_playlist("my_playlist.json")

# Dry-run mode (validate files without launching player)
player = VideoPlayer(dry_run=True)
player.play_playlist(playlist)
```

**CLI:**

```bash
# Play a single video
media-data-extractor player video.mp4

# Play all videos in a directory
media-data-extractor player ./downloads --shuffle --loop all

# Play a saved playlist
media-data-extractor player playlist.json --volume 80

# Dry-run (validate without playing)
media-data-extractor player ./downloads --dry-run
```

### Pipeline (End-to-End Research Workflow)

The pipeline chains all stages together: scrape → filter → sentiment → export → download. One command does everything:

```python
from media_data_extractor import ScrapePipeline, ScraperConfig, CommentFilter

pipeline = ScrapePipeline(
    config=ScraperConfig(max_workers=4),
    stages=["scrape", "filter", "sentiment", "export", "download"],
    export_format="csv",
    output_dir="./output",
    download_dir="./downloads",
    comment_filter=CommentFilter(min_likes=5),
    checkpoint="progress.json",
    auto_resume=True,
)

result = pipeline.run(["URL1", "URL2", "URL3"])
print(f"Processed {result.succeeded}/{result.total} videos")
print(f"Output files: {len(result.output_files)}")
for stage in result.stage_results:
    print(f"  {stage.name}: {stage.succeeded} ok, {stage.failed} failed")
```

**CLI:**

```bash
# Full pipeline: scrape + sentiment + export to CSV
media-data-extractor pipeline "URL1" "URL2" "URL3" \
  --stages scrape,sentiment,export \
  --format csv \
  --output-dir ./output

# Full pipeline with download and crash recovery
media-data-extractor pipeline --file urls.txt \
  --workers 4 \
  --stages scrape,sentiment,export,download,download_video \
  --format json \
  --output-dir ./output \
  --download-dir ./downloads \
  --video-quality 720p \
  --checkpoint progress.json \
  --auto-resume
```

**Available pipeline stages:**

| Stage | Description |
|-------|-------------|
| `scrape` | Scrape metadata, comments, transcript |
| `filter` | Filter comments by keyword/author/likes/sentiment |
| `sentiment` | Analyze comment sentiment |
| `export` | Export to JSON/CSV/JSONL/XLSX |
| `download` | Download data files (metadata, comments, transcript) |
| `download_video` | Download actual video files |

### Performance Optimizations (High Load)

For high-volume batch jobs (1000+ videos), the package includes performance utilities:

```python
from media_data_extractor import LRUCache, RateLimiter, BackoffStrategy, retry_with_backoff, chunk_list

# LRU cache — O(1) get/put, thread-safe
cache = LRUCache(maxsize=1000)
cache.put("video_id", metadata)
metadata = cache.get("video_id")  # None if not cached
value = cache.get_or_compute("key", lambda: expensive_compute())

# Rate limiter — token bucket, thread-safe
limiter = RateLimiter(rate=2.0)  # 2 operations per second
limiter.acquire()  # Blocks until allowed
if limiter.try_acquire():  # Non-blocking
    do_work()

# Exponential backoff with jitter
strat = BackoffStrategy(initial_delay=1.0, max_delay=60.0, multiplier=2.0)
delay = strat.delay(attempt=3)  # 8.0s

# Retry with backoff
result = retry_with_backoff(
    fetch_data,
    max_retries=5,
    strategy=BackoffStrategy(initial_delay=2.0),
)

# Chunk large lists for memory-efficient processing
chunks = chunk_list(list(range(10000)), chunk_size=100)
for chunk in chunks:
    process(chunk)
```

### Research Data Preparation (Fast Dataset Building)

For researchers who need to prepare datasets quickly without writing boilerplate code, the `research` module provides one-call helpers that produce ready-to-analyze output:

#### 1. Collect a Complete Dataset (one call → CSV)

```python
from media_data_extractor.research import collect_dataset

# One call → CSV with metadata, engagement, and sentiment
rows, summary = collect_dataset(
    urls=["URL1", "URL2", "URL3"],
    output_path="research_dataset.csv",
    include_sentiment=True,       # Adds sentiment columns
    include_comments=True,        # Also saves comments CSV
    include_transcripts=True,     # Also saves transcripts file
    max_comments=100,             # More comments for research
)

print(summary)
# Dataset: 3/3 videos, 300 comments, 3 transcripts, 3 sentiments, 3 files, 45.2s

# Convert to pandas DataFrame
from media_data_extractor.research import to_dataframe
df = to_dataframe(rows)
print(df[["title", "views", "likes", "sentiment_label"]].head())
```

**Output columns:** `video_id, title, channel_name, views, likes, comment_count, dislikes, upload_date, duration_seconds, category, transcript_available, sentiment_label, sentiment_positive_pct, sentiment_negative_pct, sentiment_avg_compound, engagement_rate, ...`

#### 2. Collect Comment Corpus for NLP

```python
from media_data_extractor.research import collect_comment_corpus

# All comments from all videos in one CSV — ready for NLP
comments, summary = collect_comment_corpus(
    urls=["URL1", "URL2", "URL3"],
    output_path="comment_corpus.csv",
    max_comments=500,             # Collect up to 500 per video
    include_sentiment=True,       # Per-comment sentiment label
)

# Convert to DataFrame for analysis
df = to_dataframe(comments)
print(df["sentiment_label"].value_counts())
```

#### 3. Collect Transcript Corpus for Text Analysis

```python
from media_data_extractor.research import collect_transcript_corpus

# All transcripts in one file — for LDA, embeddings, discourse analysis
transcripts, summary = collect_transcript_corpus(
    urls=["URL1", "URL2", "URL3"],
    output_path="transcripts.jsonl",
    output_format="jsonl",        # or "txt" for plain text
    include_metadata=True,        # Add title, channel, duration
)
```

#### 4. Comparative Analysis Table

```python
from media_data_extractor.research import collect_comparison_table

# Side-by-side comparison with engagement rates and sentiment
rows, summary = collect_comparison_table(
    urls=["URL1", "URL2", "URL3"],
    output_path="comparison.csv",
    include_sentiment=True,
)

# Columns: like_rate, comment_rate, engagement_rate, dislike_rate,
#          sentiment_positive_pct, sentiment_avg_compound, ...
```

#### 5. Quick Scrape (single video, fastest)

```python
from media_data_extractor.research import quick_scrape

# One call → flat dict with everything
data = quick_scrape("VIDEO_ID")
print(data["title"], data["views"], data["sentiment_label"])
```

#### 6. Pandas Integration

```python
from media_data_extractor.research import batch_to_dataframe, comments_to_dataframe
from media_data_extractor import YouTubeScraper

with YouTubeScraper() as scraper:
    batch = scraper.batch_scrape(["URL1", "URL2"])

# Direct to DataFrame
df = batch_to_dataframe(batch, include_sentiment=True)
comments_df = comments_to_dataframe(batch.results, include_sentiment=True)
```

#### Research Workflow Decision Tree

| If you need... | Use this function |
|----------------|-------------------|
| Complete dataset with everything | `collect_dataset()` |
| Comments for NLP/sentiment analysis | `collect_comment_corpus()` |
| Transcripts for text analysis | `collect_transcript_corpus()` |
| Compare videos side-by-side | `collect_comparison_table()` |
| Quick data from one video | `quick_scrape()` |
| Pandas DataFrame from batch | `batch_to_dataframe()` |
| Full pipeline (scrape→filter→export→download) | `ScrapePipeline` |

## Sample Response

Here is an example of the actual JSON output you get when scraping a real video. This was produced by running:

```bash
media-data-extractor video "https://youtu.be/ALyQ-c9_HBI" --comments 5 --pretty
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
from media_data_extractor import YouTubeScraper, ScraperConfig

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
from media_data_extractor import (
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
media-data-extractor video "https://www.youtube.com/watch?v=VIDEO_ID"

# Save to a file with pretty-printing
media-data-extractor video VIDEO_ID --out result.json --pretty

# Fetch up to 100 comments in French
media-data-extractor video VIDEO_ID --comments 100 --lang fr

# Show Chrome (for debugging)
media-data-extractor video VIDEO_ID --no-headless

# Custom timeout and retries
media-data-extractor video VIDEO_ID --timeout 60 --retries 5
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

The package is organized into focused, single-responsibility modules under `src/media_data_extractor/`. This separation of concerns makes the codebase easy to test, maintain, and extend:

<img src="https://raw.githubusercontent.com/DIP-RO/youtube-scrapper/main/docs/images/module-graph.png" alt="Module dependency graph" width="680" />

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

<img src="https://raw.githubusercontent.com/DIP-RO/youtube-scrapper/main/docs/images/scrape-flow.png" alt="Scrape flowchart" width="820" />

### Design principles

- **Network layer is isolated** — all Selenium and HTTP calls live in `client.py`. Parsing functions in `parsing.py` are pure and take dicts as input, making them trivial to test with fixtures.
- **Typed models everywhere** — the scraper never returns raw dicts. Every result is a typed dataclass with documented fields, optional fields are `None` when unavailable, and `to_dict()` produces clean JSON.
- **Defensive parsing** — YouTube changes payload shapes frequently. Every parser uses safe key lookups (`find_key`, `find_all_keys`) and returns `None` or empty lists for missing fields instead of raising exceptions.
- **No bot evasion** — the scraper detects access blocks but never tries to bypass them. If YouTube returns a CAPTCHA or consent wall, the `network.access_status` field reports it and the scrape completes with available data.
- **Configurable behavior** — `ScraperConfig` controls headless mode, timeout, retries, delays, comment limits, transcript language, and user agent. Sensible defaults work for most cases.

## Error Handling

The scraper uses a typed exception hierarchy. All exceptions inherit from `ScraperError`:

```python
from media_data_extractor import YouTubeScraper, ScraperError

try:
    with YouTubeScraper() as scraper:
        result = scraper.get_video("bad_url")
except ScraperError as e:
    print(f"Scraping failed: {e}")
```

The scraper is designed to be **defensive** — YouTube frequently changes internal payload shapes. Missing fields are returned as `None` or empty lists rather than raising exceptions. The `network.access_status` field in the result indicates whether YouTube returned an access challenge.

## Development

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=media_data_extractor

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
