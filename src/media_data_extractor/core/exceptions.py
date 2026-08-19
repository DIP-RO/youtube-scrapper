"""Exception hierarchy for media-data-extractor.

All exceptions inherit from :class:`ScraperError`, so you can catch
all package errors with a single ``except ScraperError``::

    from media_data_extractor import YouTubeScraper, ScraperError

    try:
        with YouTubeScraper() as scraper:
            result = scraper.get_video("dQw4w9WgXcQ")
    except ScraperError as e:
        print(f"Scraping failed: {e}")
"""

from __future__ import annotations


class ScraperError(Exception):
    """Base exception for all scraper errors.

    All other exceptions in this package inherit from this class.
    Catch this to handle any scraper-related error.
    """


class InvalidVideoURLError(ScraperError):
    """Raised when a URL or ID cannot be resolved to a YouTube video ID.

    This usually means the input is not a valid YouTube URL or the
    video ID is not 11 characters long.

    Example valid inputs::

        "dQw4w9WgXcQ"
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        "https://youtu.be/dQw4w9WgXcQ"
        "https://www.youtube.com/shorts/VIDEO_ID"
    """


class AccessBlockedException(ScraperError):
    """Raised when YouTube returns an access challenge.

    This happens when YouTube shows a CAPTCHA, consent page, or
    sign-in wall. The scraper does NOT bypass these — it reports
    them so you can handle them appropriately.

    Attributes:
        reasons: List of detected block reasons (e.g. ["captcha"]).
        message: Human-readable description of the block.
    """

    def __init__(self, reasons: list[str], message: str) -> None:
        self.reasons = reasons
        self.message = message
        super().__init__(message)


class SeleniumNotInstalledError(ScraperError):
    """Raised when Selenium is required but not installed.

    Fix: ``pip install selenium`` and ensure Chrome is installed.
    """


class BrowserNotInitializedError(ScraperError):
    """Raised when the scraper is used outside of a context manager.

    YouTubeScraper must be used with a ``with`` statement::

        with YouTubeScraper() as scraper:
            result = scraper.get_video("dQw4w9WgXcQ")

    Using it without ``with`` leaves the browser uninitialized.
    """


class TranscriptUnavailableError(ScraperError):
    """Raised when a transcript cannot be retrieved for a video.

    This may happen if the video has no captions, or the transcript
    language is not available.
    """


class NetworkRequestError(ScraperError):
    """Raised when a network request fails after retries."""
