from __future__ import annotations

import argparse
import json
from pathlib import Path

from .scraper import ScraperConfig, YouTubeNetworkScraper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape YouTube video metadata, comments, transcript, and summary from network payloads."
    )
    parser.add_argument("url", help="YouTube watch, shorts, or youtu.be URL")
    parser.add_argument("--comments", type=int, default=25, help="Maximum comments to fetch")
    parser.add_argument("--lang", default="en", help="Preferred transcript language code")
    parser.add_argument("--out", type=Path, help="Write JSON result to this path")
    parser.add_argument("--timeout", type=int, default=25, help="Browser timeout in seconds")
    parser.add_argument("--request-delay", type=float, default=1.5, help="Delay between fallback network requests")
    parser.add_argument("--retries", type=int, default=2, help="Page-load retries when YouTube returns a block page")
    parser.add_argument("--no-headless", action="store_true", help="Show Chrome while scraping")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = ScraperConfig(
        headless=not args.no_headless,
        timeout=args.timeout,
        max_comments=max(0, args.comments),
        transcript_language=args.lang,
        request_delay=max(0.0, args.request_delay),
        max_page_retries=max(0, args.retries),
    )

    with YouTubeNetworkScraper(config) as scraper:
        result = scraper.scrape(args.url)

    indent = 2 if args.pretty or args.out else None
    payload = json.dumps(result, ensure_ascii=False, indent=indent)

    if args.out:
        args.out.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
