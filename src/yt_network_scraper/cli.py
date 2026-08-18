"""Command-line interface for yt-network-scraper.

Usage::

    yt-network-scraper video "https://www.youtube.com/watch?v=VIDEO_ID" --comments 50 --pretty
    yt-network-scraper video dQw4w9WgXcQ --out result.json --format csv
    yt-network-scraper batch "URL1" "URL2" "URL3" --workers 4 --out batch.json
    yt-network-scraper batch --file urls.txt --workers 3 --format csv --comments-csv
    yt-network-scraper channel "@handle" --max-videos 50 --workers 4 --out channel.json
    yt-network-scraper playlist "PLxxxx" --workers 4 --out playlist.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import ScraperConfig, YouTubeScraper
from .exceptions import ScraperError
from .export import download_batch, download_video, export_batch, export_video


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="yt-network-scraper",
        description="Scrape YouTube video metadata, comments, transcript, and summary from network payloads.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # --- common args helper ---
    def add_common_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--comments", type=int, default=25, help="Maximum comments to fetch (default: 25)")
        p.add_argument("--lang", default="en", help="Preferred transcript language code (default: en)")
        p.add_argument("--out", type=Path, help="Write result to this path")
        p.add_argument("--timeout", type=int, default=25, help="Browser timeout in seconds (default: 25)")
        p.add_argument("--request-delay", type=float, default=1.5, help="Delay between fallback network requests (default: 1.5)")
        p.add_argument("--retries", type=int, default=2, help="Page-load retries (default: 2)")
        p.add_argument("--no-headless", action="store_true", help="Show Chrome while scraping")
        p.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
        p.add_argument(
            "--format",
            choices=["json", "csv", "jsonl", "txt", "xlsx", "srt"],
            default="json",
            help="Output format: json, csv, jsonl, txt, xlsx, or srt (default: json)",
        )
        p.add_argument("--comments-csv", action="store_true", help="Export comments as CSV (use with --format csv)")
        p.add_argument(
            "--download",
            type=Path,
            default=None,
            help="Download all results to this directory (creates per-video files: metadata CSV, comments CSV, transcript TXT/SRT, JSON)",
        )

    # --- video subcommand ---
    video_parser = subparsers.add_parser(
        "video",
        help="Scrape a single video by URL or ID",
        description="Scrape metadata, transcript, comments, and summary for a single YouTube video.",
    )
    video_parser.add_argument("url", help="YouTube watch URL, youtu.be URL, shorts URL, or 11-char video ID")
    add_common_args(video_parser)

    # --- batch subcommand ---
    batch_parser = subparsers.add_parser(
        "batch",
        help="Scrape multiple videos concurrently",
        description="Scrape metadata, transcript, comments, and summary for multiple YouTube videos in parallel.",
    )
    batch_parser.add_argument("urls", nargs="*", help="YouTube URLs or video IDs (space-separated)")
    batch_parser.add_argument("--file", type=Path, help="File containing one URL/ID per line")
    batch_parser.add_argument("--workers", type=int, default=3, help="Max concurrent browser instances (default: 3)")
    batch_parser.add_argument("--batch-delay", type=float, default=2.0, help="Delay between starting each task (default: 2.0)")
    add_common_args(batch_parser)
    batch_parser.add_argument("--checkpoint", type=str, default=None, help="Checkpoint JSON file for crash-resumable batching")
    batch_parser.add_argument("--auto-resume", action="store_true", help="Auto-retry on crash (requires --checkpoint)")
    batch_parser.add_argument("--max-retries", type=int, default=3, help="Max retry attempts (default: 3)")
    batch_parser.add_argument("--retry-delay", type=float, default=5.0, help="Seconds to wait before retry (default: 5.0)")

    # --- channel subcommand ---
    channel_parser = subparsers.add_parser(
        "channel",
        help="Scrape all videos from a YouTube channel",
        description="Discover video IDs from a channel and scrape them all concurrently.",
    )
    channel_parser.add_argument("channel", help="Channel URL, @handle, or channel ID (UCxxxx)")
    channel_parser.add_argument("--max-videos", type=int, default=30, help="Max videos to discover (default: 30)")
    channel_parser.add_argument("--workers", type=int, default=3, help="Max concurrent browser instances (default: 3)")
    channel_parser.add_argument("--batch-delay", type=float, default=2.0, help="Delay between starting each task (default: 2.0)")
    add_common_args(channel_parser)
    channel_parser.add_argument("--checkpoint", type=str, default=None, help="Checkpoint JSON file for crash-resumable batching")
    channel_parser.add_argument("--auto-resume", action="store_true", help="Auto-retry on crash (requires --checkpoint)")
    channel_parser.add_argument("--max-retries", type=int, default=3, help="Max retry attempts (default: 3)")
    channel_parser.add_argument("--retry-delay", type=float, default=5.0, help="Seconds to wait before retry (default: 5.0)")

    # --- playlist subcommand ---
    playlist_parser = subparsers.add_parser(
        "playlist",
        help="Scrape all videos from a YouTube playlist",
        description="Discover video IDs from a playlist and scrape them all concurrently.",
    )
    playlist_parser.add_argument("playlist", help="Playlist URL or ID (PLxxxx)")
    playlist_parser.add_argument("--max-videos", type=int, default=100, help="Max videos to discover (default: 100)")
    playlist_parser.add_argument("--workers", type=int, default=3, help="Max concurrent browser instances (default: 3)")
    playlist_parser.add_argument("--batch-delay", type=float, default=2.0, help="Delay between starting each task (default: 2.0)")
    add_common_args(playlist_parser)
    playlist_parser.add_argument("--checkpoint", type=str, default=None, help="Checkpoint JSON file for crash-resumable batching")
    playlist_parser.add_argument("--auto-resume", action="store_true", help="Auto-retry on crash (requires --checkpoint)")
    playlist_parser.add_argument("--max-retries", type=int, default=3, help="Max retry attempts (default: 3)")
    playlist_parser.add_argument("--retry-delay", type=float, default=5.0, help="Seconds to wait before retry (default: 5.0)")

    # --- download subcommand ---
    download_parser = subparsers.add_parser(
        "download",
        help="Download a YouTube video file to disk",
        description="Download a YouTube video file. Extracts stream URLs and downloads the video. For high-quality (adaptive) formats, audio and video are merged with ffmpeg if available.",
    )
    download_parser.add_argument("url", help="YouTube watch URL, youtu.be URL, or 11-char video ID")
    download_parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("."),
        help="Output file path or directory (default: current directory)",
    )
    download_parser.add_argument(
        "--quality",
        default="best",
        help="Quality: best, worst, 720p, 1080p, 4k, audio (default: best)",
    )
    download_parser.add_argument("--timeout", type=int, default=25, help="Browser timeout in seconds (default: 25)")
    download_parser.add_argument("--no-headless", action="store_true", help="Show Chrome while scraping")
    download_parser.add_argument("--list-formats", action="store_true", help="List available formats without downloading")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.  Returns a process exit code."""
    args = build_parser().parse_args(argv)

    if args.command == "video":
        return _run_video_command(args)
    if args.command == "batch":
        return _run_batch_command(args)
    if args.command == "channel":
        return _run_channel_command(args)
    if args.command == "playlist":
        return _run_playlist_command(args)
    if args.command == "download":
        return _run_download_command(args)
    return 1


def _make_config(args: argparse.Namespace, batch: bool = False) -> ScraperConfig:
    """Build ScraperConfig from CLI args."""
    kwargs: dict = dict(
        headless=not args.no_headless,
        timeout=args.timeout,
        max_comments=max(0, args.comments),
        transcript_language=args.lang,
        request_delay=max(0.0, args.request_delay),
        max_page_retries=max(0, args.retries),
    )
    if batch:
        kwargs["max_workers"] = max(1, args.workers)
        kwargs["batch_delay"] = max(0.0, args.batch_delay)
    return ScraperConfig(**kwargs)


def _write_output(content: str, args: argparse.Namespace) -> None:
    """Write content to file or stdout."""
    if args.out:
        args.out.write_text(content + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(content)


def _run_video_command(args: argparse.Namespace) -> int:
    """Execute the ``video`` subcommand."""
    config = _make_config(args)

    try:
        with YouTubeScraper(config) as scraper:
            result = scraper.get_video(args.url)
    except ScraperError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Download mode: save all files to directory
    if args.download:
        files = download_video(result, args.download)
        print(f"Downloaded {len(files)} files to {args.download}/", file=sys.stderr)
        for f in files:
            print(f"  {f.name}", file=sys.stderr)
        return 0

    if args.format == "json":
        indent = 2 if args.pretty or args.out else None
        payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=indent)
        _write_output(payload, args)
    else:
        content = export_video(result, format=args.format, comments=args.comments_csv)
        _write_output(content, args)

    return 0


def _run_batch_command(args: argparse.Namespace) -> int:
    """Execute the ``batch`` subcommand."""
    urls: list[str] = list(args.urls) if args.urls else []
    if args.file:
        file_urls = [
            line.strip()
            for line in args.file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        urls.extend(file_urls)

    if not urls:
        print("Error: no URLs provided. Pass URLs as arguments or use --file.", file=sys.stderr)
        return 1

    return _run_batch_scrape(args, urls)


def _run_channel_command(args: argparse.Namespace) -> int:
    """Execute the ``channel`` subcommand."""
    config = _make_config(args, batch=True)

    def progress(idx: int, total: int, video_id: str, status: str) -> None:
        print(f"  [{idx}/{total}] {status.upper():5s} — {video_id}", file=sys.stderr)

    print(f"Discovering videos from channel: {args.channel}...", file=sys.stderr)

    with YouTubeScraper(config) as scraper:
        video_ids = scraper.get_channel_video_ids(args.channel, args.max_videos)

    if not video_ids:
        print("No videos found on this channel.", file=sys.stderr)
        return 1

    print(f"Found {len(video_ids)} videos. Starting batch scrape...", file=sys.stderr)
    return _run_batch_scrape(args, video_ids)


def _run_playlist_command(args: argparse.Namespace) -> int:
    """Execute the ``playlist`` subcommand."""
    config = _make_config(args, batch=True)

    print(f"Discovering videos from playlist: {args.playlist}...", file=sys.stderr)

    with YouTubeScraper(config) as scraper:
        video_ids = scraper.get_playlist_video_ids(args.playlist, args.max_videos)

    if not video_ids:
        print("No videos found in this playlist.", file=sys.stderr)
        return 1

    print(f"Found {len(video_ids)} videos. Starting batch scrape...", file=sys.stderr)
    return _run_batch_scrape(args, video_ids)


def _run_batch_scrape(args: argparse.Namespace, urls: list[str]) -> int:
    """Shared logic for batch, channel, and playlist subcommands."""
    config = _make_config(args, batch=True)

    def progress(idx: int, total: int, video_id: str, status: str) -> None:
        print(f"  [{idx}/{total}] {status.upper():5s} — {video_id}", file=sys.stderr)

    if args.checkpoint:
        print(f"Checkpoint: {args.checkpoint}", file=sys.stderr)

    if args.auto_resume and not args.checkpoint:
        print("Error: --auto-resume requires --checkpoint", file=sys.stderr)
        return 1

    print(f"Scraping {len(urls)} videos with {config.max_workers} workers...", file=sys.stderr)

    if args.auto_resume:
        print(f"Auto-resume enabled: max {args.max_retries} retries, {args.retry_delay}s delay", file=sys.stderr)

    with YouTubeScraper(config) as scraper:
        if args.auto_resume:
            batch = scraper.batch_scrape_resilient(
                urls,
                progress_callback=progress,
                checkpoint=args.checkpoint,
                max_retries=max(0, args.max_retries),
                retry_delay=max(0.0, args.retry_delay),
            )
        else:
            batch = scraper.batch_scrape(urls, progress_callback=progress, checkpoint=args.checkpoint)

    print(f"\nDone: {batch.succeeded} succeeded, {batch.failed} failed, {batch.elapsed_seconds}s", file=sys.stderr)

    # Download mode: save all files to directory
    if args.download:
        files = download_batch(batch, args.download)
        print(f"Downloaded {len(files)} files to {args.download}/", file=sys.stderr)
        for f in files[:10]:
            print(f"  {f.name}", file=sys.stderr)
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more", file=sys.stderr)
        return 0 if batch.failed == 0 else 1

    if args.format == "json":
        indent = 2 if args.pretty or args.out else None
        payload = json.dumps(batch.to_dict(), ensure_ascii=False, indent=indent)
        _write_output(payload, args)
    else:
        content = export_batch(batch, format=args.format, comments=args.comments_csv)
        _write_output(content, args)

    return 0 if batch.failed == 0 else 1


def _format_bytes(size: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _run_download_command(args: argparse.Namespace) -> int:
    """Execute the ``download`` subcommand."""
    from .downloader import has_ffmpeg

    config = ScraperConfig(
        headless=not args.no_headless,
        timeout=args.timeout,
    )

    try:
        with YouTubeScraper(config) as scraper:
            # List formats mode
            if args.list_formats:
                formats = scraper.get_streams(args.url)
                if not formats:
                    print("No downloadable formats found. Video may be DRM-protected or rental.", file=sys.stderr)
                    return 1
                print(f"Available formats for {args.url}:", file=sys.stderr)
                print(f"{'ITAG':>6}  {'TYPE':<12}  {'QUALITY':<10}  {'SIZE':>10}  {'NOTE':<20}", file=sys.stderr)
                print("-" * 70, file=sys.stderr)
                for f in formats:
                    size = f"{_format_bytes(f.content_length)}" if f.content_length else "?"
                    ftype = "audio+video" if f.has_audio and f.has_video else ("video" if f.has_video else "audio")
                    print(f"{f.itag:>6}  {ftype:<12}  {(f.quality_label or f.quality):<10}  {size:>10}  {f.format_note:<20}", file=sys.stderr)
                return 0

            # Download mode
            def progress(downloaded: int, total: int, speed: float) -> None:
                if total > 0:
                    pct = downloaded * 100 / total
                    speed_str = f"{_format_bytes(int(speed))}/s" if speed > 0 else "?"
                    print(f"\r  {pct:5.1f}%  {_format_bytes(downloaded)}/{_format_bytes(total)}  {speed_str}", end="", file=sys.stderr, flush=True)

            print(f"Downloading {args.url} (quality: {args.quality})...", file=sys.stderr)
            if not has_ffmpeg() and args.quality not in ("worst", "audio"):
                print("Note: ffmpeg not found. High-quality formats will be saved as separate video+audio files.", file=sys.stderr)
                print("      Install ffmpeg to enable automatic merging: https://ffmpeg.org/download.html", file=sys.stderr)

            result = scraper.download_video_file(
                args.url,
                output_path=str(args.output),
                quality=args.quality,
                progress_callback=progress,
            )

    except ScraperError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1

    print(file=sys.stderr)  # New line after progress

    if result.success:
        print(f"Downloaded: {result.output_path}", file=sys.stderr)
        print(f"  Size: {_format_bytes(result.file_size_bytes)}", file=sys.stderr)
        print(f"  Quality: {result.quality}", file=sys.stderr)
        print(f"  Merged: {'yes (ffmpeg)' if result.merged else 'no'}", file=sys.stderr)
        if result.audio_path and not result.merged:
            print(f"  Audio: {result.audio_path}", file=sys.stderr)
        print(f"  Time: {result.elapsed_seconds:.1f}s", file=sys.stderr)
        return 0
    else:
        print(f"Download failed: {result.error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
