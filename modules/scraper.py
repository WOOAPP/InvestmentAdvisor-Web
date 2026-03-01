import logging
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from modules.url_validator import (
    validate_urls, MAX_REDIRECTS, CONNECT_TIMEOUT, READ_TIMEOUT,
    MAX_RESPONSE_BYTES,
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


def _get_session():
    global _session
    if _session is None:
        _session = _build_scraper_session()
    return _session


def scrape_url(url, max_chars=3000):
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

        # Limit rozmiaru odpowiedzi
        content_parts = []
        downloaded = 0
        for chunk in r.iter_content(chunk_size=8192, decode_unicode=False):
            downloaded += len(chunk)
            if downloaded > MAX_RESPONSE_BYTES:
                logger.warning("Przekroczono limit %d bajtów dla %s",
                               MAX_RESPONSE_BYTES, url)
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
        lines = [l.strip() for l in content.split("\n") if len(l.strip()) > 40]
        text = "\n".join(lines)
        return text[:max_chars]

    except requests.exceptions.TooManyRedirects:
        msg = f"[Zbyt wiele przekierowań dla {url}]"
        logger.warning(msg)
        return msg
    except Exception as e:
        msg = f"[Błąd pobierania {url}: {e}]"
        logger.warning(msg)
        return msg


def scrape_all(urls, max_chars_per_site=2000, trusted_domains=None):
    """Pobiera treść ze wszystkich podanych URL-i (z walidacją)."""
    if not urls:
        return ""

    valid_urls, errors = validate_urls(urls, trusted_domains)

    results = []
    for err in errors:
        results.append(f"⚠ {err}")

    for url in valid_urls:
        url = url.strip()
        if not url:
            continue
        text = scrape_url(url, max_chars=max_chars_per_site)
        results.append(f"=== ŹRÓDŁO: {url} ===\n{text}\n")
    return "\n".join(results)
