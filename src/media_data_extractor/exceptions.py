"""Exception hierarchy for media-data-extractor."""

from __future__ import annotations


class ScraperError(Exception):
    """Base exception for all scraper errors."""


class InvalidVideoURLError(ScraperError):
    """Raised when a URL or ID cannot be resolved to a YouTube video ID."""


class AccessBlockedException(ScraperError):
    """Raised when YouTube returns an access challenge (CAPTCHA, consent, sign-in, etc.)."""

    def __init__(self, reasons: list[str], message: str) -> None:
        self.reasons = reasons
        self.message = message
        super().__init__(message)


class SeleniumNotInstalledError(ScraperError):
    """Raised when Selenium is required but not installed."""


class BrowserNotInitializedError(ScraperError):
    """Raised when the scraper is used outside of a context manager."""


class TranscriptUnavailableError(ScraperError):
    """Raised when a transcript cannot be retrieved for a video."""


class NetworkRequestError(ScraperError):
    """Raised when a network request fails after retries."""
