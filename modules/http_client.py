"""Wspólny klient HTTP z timeoutami, retry i backoff.

Używany przez market_data, calendar_data, charts — wszędzie poza scraperem
(scraper ma własną logikę streaming + limity bajtów).
"""

import logging
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
        logger.error("HTTP GET %s nie powiodło się: %s", url, exc)
        raise
