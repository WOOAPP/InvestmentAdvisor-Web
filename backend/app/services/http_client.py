"""Wspólny klient HTTP z timeoutami, retry i backoff — wersja web.

Kopia z modules/http_client.py, niezależna od aplikacji desktopowej.
"""

import logging
import re
import threading
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import (
    HTTP_DEFAULT_TIMEOUT, HTTP_MAX_RETRIES, HTTP_BACKOFF_FACTOR,
    HTTP_RETRY_STATUS_CODES, HTTP_AUTH_ERROR_CODES,
    URL_MASK_PREFIX_LENGTH, URL_MASK_MIN_LENGTH,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = HTTP_DEFAULT_TIMEOUT
MAX_RETRIES = HTTP_MAX_RETRIES
BACKOFF_FACTOR = HTTP_BACKOFF_FACTOR

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

_SENSITIVE_PARAMS = re.compile(
    r"((?:apiKey|api_key|key|token|secret|password|access_token)"
    r"=)([^&\s]+)",
    re.IGNORECASE,
)


def _mask_url(url: str) -> str:
    def _replacer(m):
        val = m.group(2)
        if len(val) <= URL_MASK_MIN_LENGTH:
            return m.group(1) + "***"
        return m.group(1) + val[:URL_MASK_PREFIX_LENGTH] + "***"
    return _SENSITIVE_PARAMS.sub(_replacer, url)


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=HTTP_RETRY_STATUS_CODES,
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_session: requests.Session | None = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _session = _build_session()
    return _session


def safe_get(url: str, timeout=DEFAULT_TIMEOUT, **kwargs) -> requests.Response:
    """GET z retry, backoff i spójnym logowaniem błędów."""
    session = _get_session()
    try:
        resp = session.get(url, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        safe_url = _mask_url(url)
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in HTTP_AUTH_ERROR_CODES:
            logger.debug("HTTP %d dla %s", status, safe_url)
        else:
            logger.error("HTTP GET %s nie powiodło się: %s", safe_url, exc)
        raise
