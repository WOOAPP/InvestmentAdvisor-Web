import logging
import sys
import os
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from modules.url_validator import (
    validate_urls, MAX_REDIRECTS, CONNECT_TIMEOUT, READ_TIMEOUT,
    MAX_RESPONSE_BYTES,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from constants import (
    SCRAPER_CHUNK_SIZE, SCRAPER_DEFAULT_MAX_CHARS,
    SCRAPER_MAX_CHARS_PER_SITE, SCRAPER_MIN_LINE_LENGTH,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _build_scraper_session():
    """Sesja z limitem przekierowań."""
    s = requests.Session()
    s.headers.update(HEADERS)
    s.max_redirects = MAX_REDIRECTS
    adapter = HTTPAdapter(max_retries=0)  # scraper bez retry
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


_session = None
_session_lock = threading.Lock()


def _get_session():
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _session = _build_scraper_session()
    return _session


def scrape_url(url, max_chars=SCRAPER_DEFAULT_MAX_CHARS):
    """Pobiera pełną treść tekstową ze strony (z limitami bezpieczeństwa)."""
    try:
        session = _get_session()
        r = session.get(
            url,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            allow_redirects=True,
            stream=True,
        )
        r.raise_for_status()

        # Limit rozmiaru odpowiedzi + łączny czas pobierania
        content_parts = []
        downloaded = 0
        deadline = time.monotonic() + READ_TIMEOUT * 2  # max łączny czas streamu
        for chunk in r.iter_content(chunk_size=SCRAPER_CHUNK_SIZE, decode_unicode=False):
            downloaded += len(chunk)
            if downloaded > MAX_RESPONSE_BYTES:
                logger.warning("Przekroczono limit %d bajtów dla %s",
                               MAX_RESPONSE_BYTES, url)
                break
            if time.monotonic() > deadline:
                logger.warning("Przekroczono łączny czas pobierania dla %s", url)
                break
            content_parts.append(chunk)
        raw_html = b"".join(content_parts)

        soup = BeautifulSoup(raw_html, "html.parser")

        # Usuń zbędne elementy
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "button", "iframe", "img"]):
            tag.decompose()

        # Spróbuj znaleźć główną treść artykułu
        content = None
        for selector in ["article", "main", ".article-body", ".content",
                          ".post-content", "#content", ".entry-content"]:
            el = soup.select_one(selector)
            if el:
                content = el.get_text(separator="\n", strip=True)
                break

        if not content:
            content = soup.get_text(separator="\n", strip=True)

        # Wyczyść puste linie
        lines = [l.strip() for l in content.split("\n") if len(l.strip()) > SCRAPER_MIN_LINE_LENGTH]
        text = "\n".join(lines)
        return text[:max_chars]

    except requests.exceptions.TooManyRedirects:
        msg = f"[Zbyt wiele przekierowań dla {url}]"
        logger.warning(msg)
        return msg
    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status in (401, 403):
            msg = f"[{url}: dostęp zablokowany ({status}) — paywall/bot protection]"
            logger.info(msg)
        else:
            msg = f"[Błąd HTTP {status} dla {url}]"
            logger.warning(msg)
        return msg
    except (requests.RequestException, ConnectionError, TimeoutError,
            UnicodeDecodeError, ValueError) as e:
        msg = f"[Błąd pobierania {url}: {e}]"
        logger.warning(msg)
        return msg


def scrape_all(urls, max_chars_per_site=SCRAPER_MAX_CHARS_PER_SITE, trusted_domains=None):
    """Pobiera treść ze wszystkich podanych URL-i równolegle (z walidacją).

    Używa ThreadPoolExecutor, więc timeout jednego serwisu nie blokuje
    pozostałych – całkowity czas ≈ najwolniejszy pojedynczy request.
    """
    if not urls:
        return ""

    valid_urls, errors = validate_urls(urls, trusted_domains)

    results_map = {}
    for err in errors:
        results_map[None] = results_map.get(None, []) + [f"⚠ {err}"]

    clean_urls = [u.strip() for u in valid_urls if u.strip()]
    if clean_urls:
        per_url_timeout = CONNECT_TIMEOUT + READ_TIMEOUT + 2
        with ThreadPoolExecutor(max_workers=min(len(clean_urls), 6)) as executor:
            future_to_url = {
                executor.submit(scrape_url, url, max_chars_per_site): url
                for url in clean_urls
            }
            try:
                for future in as_completed(future_to_url,
                                           timeout=per_url_timeout):
                    url = future_to_url[future]
                    try:
                        text = future.result()
                    except Exception as exc:
                        text = f"[Błąd pobierania {url}: {exc}]"
                        logger.warning(text)
                    results_map[url] = text
            except FuturesTimeoutError:
                for future, url in future_to_url.items():
                    future.cancel()
                    if url not in results_map:
                        msg = (f"[Pominięto {url}: "
                               f"brak odpowiedzi w {per_url_timeout}s]")
                        logger.warning(msg)
                        results_map[url] = msg

    lines = results_map.pop(None, [])
    for url in clean_urls:
        if url in results_map:
            lines.append(f"=== ŹRÓDŁO: {url} ===\n{results_map[url]}\n")
    return "\n".join(lines)
