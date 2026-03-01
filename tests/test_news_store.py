"""Tests for C1 + C2: news store — dedup, normalize, SQLite."""

import unittest
import sys, os
import sqlite3
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.news_store import (
    _news_hash, _normalize_article, init_news_table,
    store_news, get_news_by_window, get_news_since,
    fetch_all_windows, NewsAuthError,
    DB_PATH,
)


class TestNewsHash(unittest.TestCase):

    def test_deterministic(self):
        h1 = _news_hash("Title", "Source", "2025-01-01T00:00:00Z")
        h2 = _news_hash("Title", "Source", "2025-01-01T00:00:00Z")
        self.assertEqual(h1, h2)

    def test_case_insensitive(self):
        h1 = _news_hash("TITLE", "SOURCE", "2025-01-01T00:00:00Z")
        h2 = _news_hash("title", "source", "2025-01-01T00:00:00Z")
        self.assertEqual(h1, h2)

    def test_different_articles_different_hash(self):
        h1 = _news_hash("Title A", "Source", "2025-01-01T00:00:00Z")
        h2 = _news_hash("Title B", "Source", "2025-01-01T00:00:00Z")
        self.assertNotEqual(h1, h2)

    def test_hash_length(self):
        h = _news_hash("Title", "Source", "2025-01-01T00:00:00Z")
        self.assertEqual(len(h), 16)


class TestNormalizeArticle(unittest.TestCase):

    def test_standard_article(self):
        raw = {
            "title": "Test Title",
            "description": "Some description",
            "source": {"name": "Reuters"},
            "publishedAt": "2025-01-01T12:00:00Z",
            "url": "https://example.com/article",
        }
        result = _normalize_article(raw, "24h")
        self.assertEqual(result["title"], "Test Title")
        self.assertEqual(result["source"], "Reuters")
        self.assertEqual(result["window"], "24h")
        self.assertIn("hash", result)

    def test_missing_fields(self):
        raw = {"title": "Minimal"}
        result = _normalize_article(raw, "7d")
        self.assertEqual(result["title"], "Minimal")
        self.assertEqual(result["source"], "")
        self.assertEqual(result["window"], "7d")

    def test_description_truncated(self):
        raw = {"title": "T", "description": "x" * 1000}
        result = _normalize_article(raw, "24h")
        self.assertLessEqual(len(result["description"]), 500)


class TestSQLiteStorage(unittest.TestCase):

    def setUp(self):
        """Use a temp DB for each test."""
        self._orig_db = os.environ.get("_TEST_DB")
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        # Monkey-patch DB_PATH
        import modules.news_store as ns
        self._orig_path = ns.DB_PATH
        ns.DB_PATH = self.db_path
        init_news_table()

    def tearDown(self):
        import modules.news_store as ns
        ns.DB_PATH = self._orig_path
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        os.rmdir(self.tmpdir)

    def test_store_and_retrieve(self):
        articles = [
            {
                "hash": "abc123",
                "title": "Test article",
                "description": "Desc",
                "source": "Reuters",
                "published_at": "2025-06-01T12:00:00Z",
                "url": "https://example.com",
                "window": "24h",
                "region": "Europa",
                "topic": "makro",
            }
        ]
        store_news(articles)
        rows = get_news_by_window("24h")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Test article")

    def test_dedup_on_hash(self):
        art = {
            "hash": "dup123",
            "title": "Duplicate",
            "description": "",
            "source": "BBC",
            "published_at": "2025-06-01T12:00:00Z",
            "url": "",
            "window": "24h",
            "region": "",
            "topic": "",
        }
        store_news([art])
        store_news([art])  # same hash → should be ignored
        rows = get_news_by_window("24h")
        self.assertEqual(len(rows), 1)

    def test_table_has_indexes(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in c.fetchall()}
        conn.close()
        self.assertIn("idx_news_published", indexes)
        self.assertIn("idx_news_source", indexes)
        self.assertIn("idx_news_window", indexes)


class TestFetchAllWindowsFailFast(unittest.TestCase):

    @patch("modules.news_store.fetch_news_window")
    def test_stops_after_auth_error(self, mock_fetch):
        """If first window returns 401, skip remaining windows."""
        mock_fetch.side_effect = NewsAuthError("401")
        result = fetch_all_windows("bad_key")
        self.assertEqual(result, [])
        # Should only attempt 1 call (24h), not all 5
        self.assertEqual(mock_fetch.call_count, 1)

    @patch("modules.news_store.fetch_news_window")
    def test_continues_on_non_auth_error(self, mock_fetch):
        """Non-auth errors should not abort remaining windows."""
        mock_fetch.return_value = []
        fetch_all_windows("good_key")
        # All 5 windows attempted
        self.assertEqual(mock_fetch.call_count, 5)

    @patch("modules.news_store.fetch_news_window")
    def test_dedup_across_windows(self, mock_fetch):
        art = {"hash": "same", "title": "T", "source": "S",
               "published_at": "2025-01-01T00:00:00Z"}
        mock_fetch.return_value = [art]
        result = fetch_all_windows("key")
        # Same hash from all 5 windows → only 1 article kept
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
