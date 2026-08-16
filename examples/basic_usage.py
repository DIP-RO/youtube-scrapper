"""Basic usage example for yt-network-scraper.

Run this script after installing the package and having Google Chrome installed:

    python examples/basic_usage.py

This example scrapes a real public YouTube video and prints every field
of the result so you can see exactly what the scraper returns.
"""

from __future__ import annotations

from yt_network_scraper import ScraperConfig, YouTubeScraper


def main() -> None:
    config = ScraperConfig(
        max_comments=5,
        transcript_language="en",
        timeout=30,
    )

    # A real public YouTube video (ATN Bangla News)
    video_url = "https://youtu.be/ALyQ-c9_HBI"

    print(f"Scraping: {video_url}\n")

    with YouTubeScraper(config) as scraper:
        result = scraper.get_video(video_url)

    # -- Metadata --
    print("=" * 60)
    print("METADATA")
    print("=" * 60)
    print(f"  Video ID:         {result.video_id}")
    print(f"  Title:            {result.metadata.title}")
    print(f"  Channel:          {result.metadata.channel_name}")
    print(f"  Channel ID:       {result.metadata.channel_id}")
    print(f"  Subscribers:      {result.metadata.channel_subscribers}")
    print(f"  Views:            {result.metadata.views}")
    print(f"  Duration:         {result.metadata.duration_seconds}s")
    print(f"  Category:         {result.metadata.category}")
    print(f"  Upload date:      {result.metadata.upload_date}")
    print(f"  Keywords:         {result.metadata.keywords[:5]}...")
    print(f"  Thumbnail:        {result.metadata.thumbnail}")

    # -- Engagement --
    print()
    print("=" * 60)
    print("ENGAGEMENT")
    print("=" * 60)
    print(f"  Likes:            {result.engagement.likes}")
    print(f"  Views:            {result.engagement.views}")
    print(f"  Comment count:    {result.engagement.comment_count}")
    print(f"  Comments scraped: {result.engagement.comment_count_scraped}")
    if result.engagement.dislikes:
        print(f"  Dislikes (RYD):   {result.engagement.dislikes.dislikes}")
        print(f"  Rating (RYD):     {result.engagement.dislikes.rating}")

    # -- Transcript --
    print()
    print("=" * 60)
    print("TRANSCRIPT")
    print("=" * 60)
    print(f"  Available:        {result.transcript.available}")
    if result.transcript.available:
        print(f"  Language:         {result.transcript.language}")
        print(f"  Auto-generated:   {result.transcript.is_auto_generated}")
        print(f"  Source:           {result.transcript.source}")
        print(f"  Segments:         {len(result.transcript.segments)}")
        print(f"  Text (first 200): {result.transcript.text[:200]}...")

    # -- Summary --
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Available:        {result.summary.available}")
    print(f"  Method:           {result.summary.method}")
    if result.summary.available:
        print(f"  Text (first 200): {result.summary.text[:200]}...")

    # -- Comments --
    print()
    print("=" * 60)
    print(f"COMMENTS ({len(result.comments)} scraped)")
    print("=" * 60)
    for i, comment in enumerate(result.comments, 1):
        print(f"  {i}. {comment.author} ({comment.published})")
        print(f"     Likes: {comment.likes} | Hearted: {comment.is_hearted} | Pinned: {comment.is_pinned}")
        print(f"     Text: {comment.text[:100]}...")
        print()

    # -- Network diagnostics --
    print("=" * 60)
    print("NETWORK DIAGNOSTICS")
    print("=" * 60)
    print(f"  Access blocked:   {result.network.access_status.blocked}")
    print(f"  Block reasons:    {result.network.access_status.reasons}")
    print(f"  API key found:    {result.network.api_key_found}")
    print(f"  Events captured:  {result.network.captured_event_count}")
    print(f"  DOM scraping:     {result.network.dom_scraping}")
    print(f"  Bot evasion:      {result.network.bot_evasion}")


if __name__ == "__main__":
    main()
