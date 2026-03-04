"""
C1 + C2: News windows fetching, deduplication, normalization, and SQLite storage.
Uses Newsdata.io API (https://newsdata.io).
"""

import hashlib
import logging
import sqlite3
import os
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import requests
from modules.http_client import safe_get

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from constants import (
    NEWS_HASH_LENGTH, NEWS_DESCRIPTION_MAX_LENGTH, NEWS_DEFAULT_PAGE_SIZE,
    NEWS_CLEANUP_DAYS, NEWS_DEFAULT_LIMIT_BY_WINDOW,
    NEWS_DEFAULT_LIMIT_SINCE, NEWS_DEFAULT_LIMIT_IN_RANGE,
)

logger = logging.getLogger(__name__)

DB_PATH = "data/advisor.db"
_db_lock = threading.RLock()


@contextmanager
def _connect():
    """Thread-safe DB connection as a context manager."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            yield conn
        finally:
            conn.close()

# ── Time windows ────────────────────────────────────────────────────
WINDOWS = {
    "24h": 1,
    "72h": 3,
    "7d": 7,
    "30d": 30,
    "90d": 90,
}


# ── SQLite schema / migration ──────────────────────────────────────
def init_news_table():
    """Create news_items table if it doesn't exist. Safe for existing DBs."""
    os.makedirs("data", exist_ok=True)
    with _connect() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS news_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                source TEXT,
                published_at TEXT,
                url TEXT,
                window TEXT,
                region TEXT,
                topic TEXT,
                fetched_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_published
            ON news_items (published_at)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_source
            ON news_items (source)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_window
            ON news_items (window)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_region
            ON news_items (region)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_topic
            ON news_items (topic)
        """)
        conn.commit()


# ── Hash / dedup ────────────────────────────────────────────────────
def _news_hash(title: str, source: str, published_at: str) -> str:
    """Deterministic hash from title+source+publishedAt."""
    raw = f"{title.strip().lower()}|{source.strip().lower()}|{published_at.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:NEWS_HASH_LENGTH]


def _normalize_article(article: dict, window: str) -> dict:
    """Normalize a single Newsdata.io article into our internal format."""
    title = article.get("title") or ""
    source = article.get("source_id") or article.get("source_name") or ""
    published_at = article.get("pubDate") or ""
    return {
        "hash": _news_hash(title, source, published_at),
        "title": title,
        "description": (article.get("description") or "")[:NEWS_DESCRIPTION_MAX_LENGTH],
        "source": source,
        "published_at": published_at,
        "url": article.get("link") or "",
        "window": window,
    }


# ── Fetch from Newsdata.io with time windows ─────────────────────────

class NewsAuthError(Exception):
    """Raised when Newsdata.io returns 401/403 — bad key or plan limit."""


def fetch_news_window(api_key: str, window: str, days: int,
                      query: str = "geopolitics economy markets finance",
                      language: str = "en",
                      page_size: int = NEWS_DEFAULT_PAGE_SIZE) -> list[dict]:
    """Fetch news for a single time window from Newsdata.io.

    Uses /api/1/latest for recent windows (≤3 days) and /api/1/archive
    for longer ranges (7d+).  Falls back to /latest if archive returns
    error (free plans may not have archive access).

    Raises NewsAuthError on 401/403 so callers can fail fast.
    """
    if not api_key:
        return []

    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    to_date = now.strftime("%Y-%m-%d")

    # Choose endpoint: latest (≤3d) vs archive (7d+)
    endpoint = "latest" if days <= 3 else "archive"

    try:
        articles = _newsdata_request(
            api_key, endpoint, query, language, from_date, to_date,
            page_size, window)

        # Fallback: if archive failed (empty + free plan), try latest
        if not articles and endpoint == "archive":
            articles = _newsdata_request(
                api_key, "latest", query, language, from_date, to_date,
                page_size, window)

        return articles
    except NewsAuthError:
        raise
    except (requests.RequestException, ValueError, KeyError) as e:
        logger.warning("Błąd pobierania newsów (window=%s): %s", window, e)
        return []


def _newsdata_request(api_key: str, endpoint: str, query: str,
                      language: str, from_date: str, to_date: str,
                      page_size: int, window: str) -> list[dict]:
    """Low-level Newsdata.io request. Returns list of normalized articles."""
    base = f"https://newsdata.io/api/1/{endpoint}"
    url = (
        f"{base}?apikey={api_key}"
        f"&q={query}&language={language}"
        f"&from_date={from_date}&to_date={to_date}"
        f"&size={min(page_size, NEWS_DEFAULT_PAGE_SIZE)}"
    )
    try:
        r = safe_get(url)
        data = r.json()

        # Newsdata.io returns {"status": "error", "results": {"code": ...}}
        if data.get("status") == "error":
            err = data.get("results", {})
            code = err.get("code") if isinstance(err, dict) else ""
            msg = err.get("message", "") if isinstance(err, dict) else str(err)
            if code in ("Unauthorized", "ForbiddenAccess"):
                raise NewsAuthError(f"Newsdata.io {code}: {msg}")
            logger.warning("Newsdata.io error (window=%s): %s — %s",
                           window, code, msg)
            return []

        articles = []
        for a in data.get("results", []):
            if not isinstance(a, dict):
                continue
            if not a.get("title"):
                continue
            # Skip duplicates flagged by Newsdata.io
            if a.get("duplicate") is True:
                continue
            articles.append(_normalize_article(a, window))
        return articles

    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status in (401, 403):
            logger.warning("Newsdata.io %d (window=%s) — sprawdź klucz API",
                           status, window)
            raise NewsAuthError(f"Newsdata.io HTTP {status}") from e
        logger.warning("Newsdata.io błąd HTTP (window=%s): %s", window, e)
        return []


def fetch_all_windows(api_key: str, **kwargs) -> list[dict]:
    """Fetch news for all time windows, deduplicate by hash.

    Fail-fast: if the first window returns 401/403 (bad key), skip the rest.
    """
    seen_hashes: set[str] = set()
    all_articles: list[dict] = []
    # Fetch shortest window first (most recent) → they get priority
    for window, days in sorted(WINDOWS.items(), key=lambda x: x[1]):
        try:
            articles = fetch_news_window(api_key, window, days, **kwargs)
        except NewsAuthError:
            logger.warning("Klucz Newsdata.io nieprawidłowy lub plan nie "
                           "obsługuje okna %s — pomijam pozostałe okna",
                           window)
            break
        for art in articles:
            if art["hash"] not in seen_hashes:
                seen_hashes.add(art["hash"])
                all_articles.append(art)
    return all_articles


# ── SQLite persistence ──────────────────────────────────────────────
def store_news(articles: list[dict]):
    """Insert articles into news_items, skip duplicates (ON CONFLICT IGNORE)."""
    if not articles:
        return
    _ensure_table()
    with _connect() as conn:
        c = conn.cursor()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        for art in articles:
            try:
                c.execute("""
                    INSERT OR IGNORE INTO news_items
                        (hash, title, description, source, published_at, url, window,
                         region, topic, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    art["hash"], art["title"], art.get("description", ""),
                    art["source"], art["published_at"], art.get("url", ""),
                    art.get("window", ""), art.get("region", ""),
                    art.get("topic", ""), now,
                ))
            except (sqlite3.Error, KeyError) as e:
                logger.warning("store_news skip: %s", e)
        conn.commit()


def get_news_by_window(window: str, limit: int = NEWS_DEFAULT_LIMIT_BY_WINDOW) -> list[dict]:
    """Retrieve stored news for a given time window."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT * FROM news_items
            WHERE window = ?
            ORDER BY published_at DESC
            LIMIT ?
        """, (window, limit))
        return [dict(r) for r in c.fetchall()]


def get_news_since(hours: int, limit: int = NEWS_DEFAULT_LIMIT_SINCE) -> list[dict]:
    """Retrieve news published in the last N hours."""
    _ensure_table()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT * FROM news_items
            WHERE published_at >= ?
            ORDER BY published_at DESC
            LIMIT ?
        """, (since, limit))
        return [dict(r) for r in c.fetchall()]


def get_news_in_range(days_from: int, days_to: int = 0,
                      limit: int = NEWS_DEFAULT_LIMIT_IN_RANGE) -> list[dict]:
    """Retrieve news between days_from and days_to ago (0 = now)."""
    _ensure_table()
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days_from)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now - timedelta(days=days_to)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT * FROM news_items
            WHERE published_at >= ? AND published_at <= ?
            ORDER BY published_at DESC
            LIMIT ?
        """, (start, end, limit))
        return [dict(r) for r in c.fetchall()]


def cleanup_old_news(days: int = NEWS_CLEANUP_DAYS):
    """Delete news older than N days."""
    _ensure_table()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    with _connect() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM news_items WHERE published_at < ?", (cutoff,))
        conn.commit()


_table_initialized = False
_init_lock = threading.Lock()


def _ensure_table():
    """Lazy init — create news_items table on first DB access, not on import."""
    global _table_initialized
    if _table_initialized:
        return
    with _init_lock:
        if not _table_initialized:
            init_news_table()
            _table_initialized = True
