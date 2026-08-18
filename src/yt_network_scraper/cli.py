"""Command-line interface for yt-network-scraper.

Usage::

    yt-network-scraper video "https://www.youtube.com/watch?v=VIDEO_ID" --comments 50 --pretty
    yt-network-scraper video dQw4w9WgXcQ --out result.json
    yt-network-scraper batch "URL1" "URL2" "URL3" --workers 4 --out batch.json
    yt-network-scraper batch --file urls.txt --workers 3 --pretty
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import ScraperConfig, YouTubeScraper
from .exceptions import ScraperError


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="yt-network-scraper",
        description="Scrape YouTube video metadata, comments, transcript, and summary from network payloads.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # --- video subcommand ---
    video_parser = subparsers.add_parser(
        "video",
        help="Scrape a single video by URL or ID",
        description="Scrape metadata, transcript, comments, and summary for a single YouTube video.",
    )
    video_parser.add_argument("url", help="YouTube watch URL, youtu.be URL, shorts URL, or 11-char video ID")
    video_parser.add_argument("--comments", type=int, default=25, help="Maximum comments to fetch (default: 25)")
    video_parser.add_argument("--lang", default="en", help="Preferred transcript language code (default: en)")
    video_parser.add_argument("--out", type=Path, help="Write JSON result to this path")
    video_parser.add_argument("--timeout", type=int, default=25, help="Browser timeout in seconds (default: 25)")
    video_parser.add_argument(
        "--request-delay",
        type=float,
        default=1.5,
        help="Delay between fallback network requests in seconds (default: 1.5)",
    )
    video_parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Page-load retries when YouTube returns a block page (default: 2)",
    )
    video_parser.add_argument("--no-headless", action="store_true", help="Show Chrome while scraping (for debugging)")
    video_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    # --- batch subcommand ---
    batch_parser = subparsers.add_parser(
        "batch",
        help="Scrape multiple videos concurrently",
        description="Scrape metadata, transcript, comments, and summary for multiple YouTube videos in parallel.",
    )
    batch_parser.add_argument("urls", nargs="*", help="YouTube URLs or video IDs (space-separated)")
    batch_parser.add_argument("--file", type=Path, help="File containing one URL/ID per line")
    batch_parser.add_argument("--workers", type=int, default=3, help="Max concurrent browser instances (default: 3)")
    batch_parser.add_argument("--batch-delay", type=float, default=2.0, help="Delay between starting each task in seconds (default: 2.0)")
    batch_parser.add_argument("--comments", type=int, default=25, help="Maximum comments to fetch per video (default: 25)")
    batch_parser.add_argument("--lang", default="en", help="Preferred transcript language code (default: en)")
    batch_parser.add_argument("--out", type=Path, help="Write JSON result to this path")
    batch_parser.add_argument("--timeout", type=int, default=25, help="Browser timeout in seconds (default: 25)")
    batch_parser.add_argument("--request-delay", type=float, default=1.5, help="Delay between fallback network requests (default: 1.5)")
    batch_parser.add_argument("--retries", type=int, default=2, help="Page-load retries (default: 2)")
    batch_parser.add_argument("--no-headless", action="store_true", help="Show Chrome while scraping")
    batch_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    batch_parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Path to checkpoint JSON file for crash-resumable batching. Completed videos are saved incrementally and skipped on re-run.",
    )
    batch_parser.add_argument(
        "--auto-resume",
        action="store_true",
        help="Enable automatic crash recovery. On any crash, the batch retries from the checkpoint (up to --max-retries times).",
    )
    batch_parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retry attempts when --auto-resume is enabled (default: 3).",
    )
    batch_parser.add_argument(
        "--retry-delay",
        type=float,
        default=5.0,
        help="Seconds to wait before retrying after a crash (default: 5.0).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.  Returns a process exit code."""
    args = build_parser().parse_args(argv)

    if args.command == "video":
        return _run_video_command(args)
    if args.command == "batch":
        return _run_batch_command(args)
    return 1


def _run_video_command(args: argparse.Namespace) -> int:
    """Execute the ``video`` subcommand."""
    config = ScraperConfig(
        headless=not args.no_headless,
        timeout=args.timeout,
        max_comments=max(0, args.comments),
        transcript_language=args.lang,
        request_delay=max(0.0, args.request_delay),
        max_page_retries=max(0, args.retries),
    )

    try:
        with YouTubeScraper(config) as scraper:
            result = scraper.get_video(args.url)
    except ScraperError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    indent = 2 if args.pretty or args.out else None
    payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=indent)

    if args.out:
        args.out.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(payload)

    return 0


def _run_batch_command(args: argparse.Namespace) -> int:
    """Execute the ``batch`` subcommand."""
    # Collect URLs from arguments and/or file
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

    config = ScraperConfig(
        headless=not args.no_headless,
        timeout=args.timeout,
        max_comments=max(0, args.comments),
        transcript_language=args.lang,
        request_delay=max(0.0, args.request_delay),
        max_page_retries=max(0, args.retries),
        max_workers=max(1, args.workers),
        batch_delay=max(0.0, args.batch_delay),
    )

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

    indent = 2 if args.pretty or args.out else None
    payload = json.dumps(batch.to_dict(), ensure_ascii=False, indent=indent)

    if args.out:
        args.out.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(payload)

    return 0 if batch.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
