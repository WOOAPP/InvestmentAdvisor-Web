"""Tests for macro_trend orchestrator and ai_engine integration."""

import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.macro_trend import (
    _slim_articles, _summarize_geo, _slim_trend,
    format_macro_payload_for_llm,
)
from modules.ai_engine import _build_macro_prompt, _build_legacy_prompt


def _sample_payload():
    return {
        "news_dnia": {
            "selected_news": {
                "title": "Fed cuts rates",
                "source": "Reuters",
                "region": "Ameryka Pn.",
                "topic": "banki centralne",
            },
            "score": 42.5,
            "justification": [
                "Źródło: Reuters (waga: 10/10)",
                "Aktualność: 9.8/10",
                "Temat: banki centralne (waga: 3.0)",
            ],
            "watch_signals": [
                "Decyzje stóp procentowych",
                "Dane z USA i retoryka Fed",
            ],
        },
        "geo_24h": {
            "Ameryka Pn.": [
                {"title": "Fed cuts", "source": "Reuters", "topic": "banki centralne"},
            ],
            "Europa": [
                {"title": "ECB holds", "source": "Bloomberg", "topic": "banki centralne"},
            ],
        },
        "articles_24h": [
            {"title": "Fed cuts", "source": "Reuters",
             "published_at": "2025-01-01T12:00", "region": "Ameryka Pn.",
             "topic": "banki centralne", "description": "The Federal Reserve"},
        ],
        "trend": {
            "aggregates": {
                "24h": {"count": 15, "top_regions": [{"region": "Ameryka Pn.", "count": 8}],
                         "top_topics": [{"topic": "banki centralne", "count": 6}],
                         "top_keywords": ["fed", "rates"]},
                "7d": {"count": 40, "top_regions": [{"region": "Europa", "count": 15}],
                        "top_topics": [{"topic": "makro", "count": 12}],
                        "top_keywords": ["gdp", "growth"]},
                "30d": {"count": 100, "top_regions": [], "top_topics": [], "top_keywords": []},
                "90d": {"count": 200, "top_regions": [], "top_topics": [], "top_keywords": []},
            },
            "diffs": [
                {"window": "7d vs 24h", "signal": "anomalia",
                 "details": {"dominant_topic_24h": "banki centralne",
                             "dominant_topic_window": "makro",
                             "dominant_region_24h": "Ameryka Pn.",
                             "dominant_region_window": "Europa",
                             "new_topics_in_24h": [],
                             "new_keywords": ["fed"],
                             "fading_keywords": ["gdp"]}},
            ],
        },
        "stats": {
            "total_fetched": 150,
            "articles_24h": 15,
            "articles_7d": 40,
            "articles_30d": 100,
            "articles_90d": 200,
        },
    }


class TestSlimArticles(unittest.TestCase):

    def test_keeps_only_needed_fields(self):
        articles = [{
            "title": "Test", "source": "Reuters",
            "published_at": "2025-01-01T12:00:00Z",
            "region": "Europa", "topic": "makro",
            "description": "Some long description text here " * 10,
            "url": "https://example.com",  # should be stripped
            "hash": "abc123",              # should be stripped
        }]
        result = _slim_articles(articles)
        self.assertEqual(len(result), 1)
        self.assertNotIn("url", result[0])
        self.assertNotIn("hash", result[0])
        self.assertLessEqual(len(result[0]["description"]), 120)


class TestSummarizeGeo(unittest.TestCase):

    def test_max_5_per_region(self):
        geo = {
            "Europa": [{"title": f"News {i}", "source": "S", "topic": "t"}
                       for i in range(10)]
        }
        result = _summarize_geo(geo)
        self.assertEqual(len(result["Europa"]), 5)


class TestSlimTrend(unittest.TestCase):

    def test_limits_regions_and_topics(self):
        trend = {
            "aggregates": {
                "24h": {
                    "count": 10,
                    "top_regions": [{"region": f"R{i}", "count": i} for i in range(6)],
                    "top_topics": [{"topic": f"T{i}", "count": i} for i in range(8)],
                    "top_keywords": [f"kw{i}" for i in range(10)],
                },
            },
            "diffs": [],
        }
        result = _slim_trend(trend)
        self.assertEqual(len(result["aggregates"]["24h"]["top_regions"]), 3)
        self.assertEqual(len(result["aggregates"]["24h"]["top_topics"]), 3)
        self.assertEqual(len(result["aggregates"]["24h"]["top_keywords"]), 5)


class TestFormatMacroPayload(unittest.TestCase):

    def test_contains_all_sections(self):
        text = format_macro_payload_for_llm(_sample_payload())
        self.assertIn("NEWS DNIA", text)
        self.assertIn("GEO 24H", text)
        self.assertIn("NEWSY 24-72H", text)
        self.assertIn("TREND NARRACJI", text)
        self.assertIn("Porównanie trendów", text)

    def test_empty_payload(self):
        text = format_macro_payload_for_llm({})
        self.assertIsInstance(text, str)


class TestBuildMacroPrompt(unittest.TestCase):

    def test_contains_structure_instructions(self):
        prompt = _build_macro_prompt("market data", "macro text")
        self.assertIn("NEWS DNIA", prompt)
        self.assertIn("GEO 24H", prompt)
        self.assertIn("PORÓWNANIE TRENDU", prompt)
        self.assertIn("SCENARIUSZE", prompt)
        self.assertIn("PERSPEKTYWA RUCHU", prompt)
        self.assertIn("NIE porada", prompt)
        self.assertIn("market data", prompt)
        self.assertIn("macro text", prompt)


class TestBuildLegacyPrompt(unittest.TestCase):

    def test_backward_compat(self):
        news = [{"source": "Reuters", "title": "Test", "description": "Desc"}]
        prompt = _build_legacy_prompt("summary", news)
        self.assertIn("summary", prompt)
        self.assertIn("Reuters", prompt)
        self.assertIn("AKTUALNE WIADOMOŚCI", prompt)


if __name__ == "__main__":
    unittest.main()
