"""Wspólny klient HTTP z timeoutami, retry i backoff.

Używany przez market_data, calendar_data, charts — wszędzie poza scraperem
(scraper ma własną logikę streaming + limity bajtów).
"""

import logging
import re
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = (8, 15)  # (connect, read) w sekundach
MAX_RETRIES = 2
BACKOFF_FACTOR = 1.0  # 1s, 2s między próbami

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Patterns to mask in URLs before logging
_SENSITIVE_PARAMS = re.compile(
    r"((?:apiKey|api_key|key|token|secret|password|access_token)"
    r"=)([^&\s]+)",
    re.IGNORECASE,
)


def _mask_url(url: str) -> str:
    """Replace sensitive query params in URL with masked version for logs."""
    def _replacer(m):
        val = m.group(2)
        if len(val) <= 6:
            return m.group(1) + "***"
        return m.group(1) + val[:4] + "***"
    return _SENSITIVE_PARAMS.sub(_replacer, url)


def _build_session() -> requests.Session:
    """Tworzy sesję z retry i backoff."""
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# Singleton session — thread-safe z urllib3
_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = _build_session()
    return _session


def safe_get(url: str, timeout=DEFAULT_TIMEOUT, **kwargs) -> requests.Response:
    """GET z retry, backoff i spójnym logowaniem błędów.

    Raises requests.RequestException na nienaprawialny błąd.
    """
    session = _get_session()
    try:
        resp = session.get(url, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        safe_url = _mask_url(url)
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (401, 403):
            logger.warning("HTTP %d dla %s", status, safe_url)
        else:
            logger.error("HTTP GET %s nie powiodło się: %s", safe_url, exc)
        raise
