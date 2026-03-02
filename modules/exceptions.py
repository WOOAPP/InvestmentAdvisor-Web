"""Application-specific exception classes.

Replacing bare `except Exception` with targeted catches improves
debuggability and prevents accidentally swallowing programming errors.
"""


class DataFetchError(Exception):
    """Raised when fetching market data, FX rates, or external APIs fails."""


class AIProviderError(Exception):
    """Raised when an AI provider call fails (API error, timeout, etc.)."""


class ScraperError(Exception):
    """Raised when scraping a URL fails for non-HTTP reasons."""
