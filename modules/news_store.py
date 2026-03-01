"""
C1 + C2: News windows fetching, deduplication, normalization, and SQLite storage.
"""

import hashlib
import logging
import sqlite3
import os
from datetime import datetime, timedelta

import requests
from modules.http_client import safe_get

logger = logging.getLogger(__name__)

DB_PATH = "data/advisor.db"

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
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()


# ── Hash / dedup ────────────────────────────────────────────────────
def _news_hash(title: str, source: str, published_at: str) -> str:
    """Deterministic hash from title+source+publishedAt."""
    raw = f"{title.strip().lower()}|{source.strip().lower()}|{published_at.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _normalize_article(article: dict, window: str) -> dict:
    """Normalize a single NewsAPI article into our internal format."""
    title = article.get("title") or ""
    source = article.get("source", {}).get("name", "") if isinstance(article.get("source"), dict) else str(article.get("source", ""))
    published_at = article.get("publishedAt", "")
    return {
        "hash": _news_hash(title, source, published_at),
        "title": title,
        "description": (article.get("description") or "")[:500],
        "source": source,
        "published_at": published_at,
        "url": article.get("url", ""),
        "window": window,
    }


# ── Fetch from NewsAPI with time windows ────────────────────────────

class NewsAuthError(Exception):
    """Raised when NewsAPI returns 401/403 — bad key or plan limit."""


def fetch_news_window(api_key: str, window: str, days: int,
                      query: str = "geopolitics economy markets finance",
                      language: str = "en",
                      page_size: int = 30) -> list[dict]:
    """Fetch news for a single time window. Returns normalized articles.

    Raises NewsAuthError on 401/403 so callers can fail fast.
    """
    if not api_key:
        return []
    now = datetime.utcnow()
    from_date = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        url = (
            f"https://newsapi.org/v2/everything?"
            f"q={query}&language={language}&sortBy=publishedAt"
            f"&from={from_date}&to={to_date}"
            f"&pageSize={page_size}&apiKey={api_key}"
        )
        r = safe_get(url)
        data = r.json()
        articles = []
        for a in data.get("articles", []):
            if not a.get("title"):
                continue
            articles.append(_normalize_article(a, window))
        return articles
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status in (401, 403):
            logger.warning("NewsAPI %d (window=%s) — sprawdź klucz API",
                           status, window)
            raise NewsAuthError(f"NewsAPI HTTP {status}") from e
        logger.warning("NewsAPI błąd (window=%s): %s", window, e)
        return []
    except Exception as e:
        logger.warning("Błąd pobierania newsów (window=%s): %s", window, e)
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
            logger.warning("Klucz NewsAPI nieprawidłowy lub plan nie obsługuje "
                           "okna %s — pomijam pozostałe okna", window)
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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
        except Exception as e:
            logger.warning("store_news skip: %s", e)
    conn.commit()
    conn.close()


def get_news_by_window(window: str, limit: int = 50) -> list[dict]:
    """Retrieve stored news for a given time window."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM news_items
        WHERE window = ?
        ORDER BY published_at DESC
        LIMIT ?
    """, (window, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_news_since(hours: int, limit: int = 100) -> list[dict]:
    """Retrieve news published in the last N hours."""
    since = (datetime.utcnow() - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM news_items
        WHERE published_at >= ?
        ORDER BY published_at DESC
        LIMIT ?
    """, (since, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_news_in_range(days_from: int, days_to: int = 0,
                      limit: int = 200) -> list[dict]:
    """Retrieve news between days_from and days_to ago (0 = now)."""
    now = datetime.utcnow()
    start = (now - timedelta(days=days_from)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now - timedelta(days=days_to)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM news_items
        WHERE published_at >= ? AND published_at <= ?
        ORDER BY published_at DESC
        LIMIT ?
    """, (start, end, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def cleanup_old_news(days: int = 100):
    """Delete news older than N days."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM news_items WHERE published_at < ?", (cutoff,))
    conn.commit()
    conn.close()


# Init table on import
init_news_table()
