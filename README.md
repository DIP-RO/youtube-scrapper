# YouTube Network Scraper

Headless Selenium, network-first YouTube video scraper.

It avoids DOM scraping. Selenium opens the video page in headless Chrome, captures network responses through Chrome DevTools/performance logs, extracts YouTube's initial network payloads, then uses network endpoints for:

- video metadata: title, description, views, author/channel name, channel id, publish/upload dates, duration, tags
- channel metadata visible in the watch payload, including subscriber text when YouTube sends it
- dislike counts from the Return YouTube Dislike API
- comments through YouTube continuation API calls
- transcript/captions through YouTube timedtext caption URLs
- automatic local summary from transcript text, falling back to description

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Chrome must be installed. Selenium Manager will fetch/use a matching driver automatically in recent Selenium versions.

## Usage

```bash
yt-network-scraper "https://www.youtube.com/watch?v=VIDEO_ID" --comments 50 --out result.json
```

Or:

```bash
python -m yt_network_scraper.cli "https://youtu.be/VIDEO_ID" --comments 25
```

Useful options:

- `--comments N`: maximum comments to fetch
- `--lang en`: preferred transcript language
- `--no-headless`: run Chrome visibly for debugging
- `--timeout 25`: browser wait timeout
- `--pretty`: print indented JSON to stdout

## Notes

YouTube changes internal payload shapes often. This scraper keeps parsing defensive and returns `null`/empty lists where a field is not available. Some fields, especially subscriber counts and dislikes, may be hidden, region-limited, or unavailable for specific videos.
