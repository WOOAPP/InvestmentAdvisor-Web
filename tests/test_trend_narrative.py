"""Tests for C5: trend narrative aggregates and diffs."""

import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.trend_narrative import (
    _aggregate_window, _compare_windows, build_trend_payload, build_geo_24h,
)


def _art(title="News", region="Świat", topic="makro"):
    return {"title": title, "region": region, "topic": topic,
            "published_at": "2025-01-01T12:00:00Z", "source": "Test"}


class TestAggregateWindow(unittest.TestCase):

    def test_empty(self):
        result = _aggregate_window([])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["top_regions"], [])

    def test_counts(self):
        articles = [
            _art(region="Europa", topic="makro"),
            _art(region="Europa", topic="inflacja/stopy"),
            _art(region="Azja", topic="makro"),
        ]
        result = _aggregate_window(articles)
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["top_regions"][0]["region"], "Europa")
        self.assertEqual(result["top_regions"][0]["count"], 2)

    def test_keywords_extracted(self):
        articles = [_art(title="Bitcoin soars again"),
                     _art(title="Bitcoin drops sharply")]
        result = _aggregate_window(articles)
        self.assertIn("bitcoin", result["top_keywords"])


class TestCompareWindows(unittest.TestCase):

    def test_continuation(self):
        base = {
            "count": 5,
            "top_regions": [{"region": "Europa", "count": 3}],
            "top_topics": [{"topic": "makro", "count": 4}],
            "top_keywords": ["gdp", "growth"],
        }
        comp = {
            "count": 20,
            "top_regions": [{"region": "Europa", "count": 12}],
            "top_topics": [{"topic": "makro", "count": 15}],
            "top_keywords": ["gdp", "growth", "inflation"],
        }
        result = _compare_windows(base, comp, "7d vs 24h")
        self.assertEqual(result["window"], "7d vs 24h")
        self.assertEqual(result["signal"], "kontynuacja")

    def test_empty_data(self):
        result = _compare_windows(
            {"count": 0, "top_regions": [], "top_topics": [], "top_keywords": []},
            {"count": 0, "top_regions": [], "top_topics": [], "top_keywords": []},
            "7d vs 24h")
        self.assertEqual(result["signal"], "brak danych")


class TestBuildTrendPayload(unittest.TestCase):

    def test_structure(self):
        arts = [_art()]
        result = build_trend_payload(arts, arts, arts, arts)
        self.assertIn("aggregates", result)
        self.assertIn("diffs", result)
        self.assertIn("24h", result["aggregates"])
        self.assertIn("7d", result["aggregates"])
        self.assertIn("30d", result["aggregates"])
        self.assertIn("90d", result["aggregates"])
        self.assertEqual(len(result["diffs"]), 3)


class TestBuildGeo24h(unittest.TestCase):

    def test_groups_by_region(self):
        articles = [
            _art(region="Europa"),
            _art(region="Europa"),
            _art(region="Azja"),
        ]
        geo = build_geo_24h(articles)
        self.assertEqual(len(geo["Europa"]), 2)
        self.assertEqual(len(geo["Azja"]), 1)

    def test_empty(self):
        self.assertEqual(build_geo_24h([]), {})


if __name__ == "__main__":
    unittest.main()
