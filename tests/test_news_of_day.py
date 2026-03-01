"""Tests for C4: News dnia scoring — minimum 8 test cases as required."""

import unittest
import sys, os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.news_of_day import (
    score_article, select_news_of_day,
    _source_score, _recency_score, _keyword_score, _topic_score,
    SOURCE_WEIGHTS, TOPIC_WEIGHTS,
)


def _make_article(title="Test headline", source="Reuters",
                  published_at=None, topic="makro", region="Świat",
                  description=""):
    if published_at is None:
        published_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "title": title,
        "source": source,
        "published_at": published_at,
        "topic": topic,
        "region": region,
        "description": description,
    }


class TestSourceScore(unittest.TestCase):

    def test_reuters_high(self):
        self.assertEqual(_source_score("Reuters"), 10.0)

    def test_unknown_source_default(self):
        self.assertEqual(_source_score("Random Blog"), 3.0)

    def test_partial_match(self):
        # "bbc" is in "BBC News"
        self.assertEqual(_source_score("BBC News"), 8.0)


class TestRecencyScore(unittest.TestCase):

    def test_very_recent(self):
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        score = _recency_score(now)
        self.assertGreater(score, 9.0)

    def test_old_72h(self):
        old = (datetime.utcnow() - timedelta(hours=72)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        score = _recency_score(old)
        self.assertLessEqual(score, 2.0)

    def test_mid_age(self):
        mid = (datetime.utcnow() - timedelta(hours=36)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        score = _recency_score(mid)
        self.assertGreater(score, 4.0)
        self.assertLess(score, 7.0)


class TestKeywordScore(unittest.TestCase):

    def test_no_impact_keywords(self):
        self.assertEqual(_keyword_score("Market update today"), 0.0)

    def test_single_impact_keyword(self):
        score = _keyword_score("Fed announces rate cut")
        self.assertGreater(score, 0)

    def test_multiple_impact_keywords(self):
        score = _keyword_score("War crisis crash recession")
        self.assertGreaterEqual(score, 3.0)

    def test_cap_at_6(self):
        score = _keyword_score(
            "war crash recession crisis default collapse bank run nuclear")
        self.assertLessEqual(score, 6.0)


class TestTopicScore(unittest.TestCase):

    def test_banki_centralne_highest(self):
        self.assertEqual(_topic_score("banki centralne"), 3.0)

    def test_inne_lowest(self):
        self.assertEqual(_topic_score("inne"), 0.5)


class TestScoreArticle(unittest.TestCase):
    """Integration tests for the composite scoring function."""

    def test_reuters_recent_crisis(self):
        """High-quality source + recent + crisis keywords → high score."""
        art = _make_article(
            title="War escalates as sanctions imposed",
            source="Reuters",
            topic="konflikt",
        )
        score = score_article(art)
        self.assertGreater(score, 30.0)

    def test_unknown_old_bland(self):
        """Unknown source + old + no keywords → low score."""
        old_date = (datetime.utcnow() - timedelta(hours=70)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        art = _make_article(
            title="Regular market update",
            source="Unknown Blog",
            published_at=old_date,
            topic="inne",
        )
        score = score_article(art)
        self.assertLess(score, 15.0)

    def test_bloomberg_rate_decision(self):
        """Bloomberg + rate decision topic → strong score."""
        art = _make_article(
            title="Rate decision surprises markets",
            source="Bloomberg",
            topic="banki centralne",
        )
        score = score_article(art)
        self.assertGreater(score, 30.0)

    def test_scoring_order_preserved(self):
        """Higher-impact article should score higher than bland one."""
        high = _make_article(
            title="Fed crash rate cut emergency",
            source="Reuters",
            topic="banki centralne",
        )
        low = _make_article(
            title="Sunny weather in Madrid",
            source="Local News",
            topic="inne",
        )
        self.assertGreater(score_article(high), score_article(low))


class TestSelectNewsOfDay(unittest.TestCase):

    def test_empty_returns_none(self):
        self.assertIsNone(select_news_of_day([]))

    def test_single_article(self):
        arts = [_make_article(title="Only news")]
        result = select_news_of_day(arts)
        self.assertIsNotNone(result)
        self.assertEqual(result["selected_news"]["title"], "Only news")

    def test_best_article_selected(self):
        weak = _make_article(
            title="Regular update",
            source="Unknown",
            topic="inne",
            published_at=(datetime.utcnow() - timedelta(hours=60)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
        )
        strong = _make_article(
            title="Fed emergency rate cut shocks markets",
            source="Reuters",
            topic="banki centralne",
        )
        result = select_news_of_day([weak, strong])
        self.assertEqual(result["selected_news"]["title"], strong["title"])

    def test_result_structure(self):
        art = _make_article(title="Test", topic="makro", region="Europa")
        result = select_news_of_day([art])
        self.assertIn("selected_news", result)
        self.assertIn("score", result)
        self.assertIn("justification", result)
        self.assertIn("watch_signals", result)
        self.assertIsInstance(result["justification"], list)
        self.assertGreaterEqual(len(result["justification"]), 3)
        self.assertLessEqual(len(result["justification"]), 6)
        self.assertIsInstance(result["watch_signals"], list)
        self.assertGreaterEqual(len(result["watch_signals"]), 2)
        self.assertLessEqual(len(result["watch_signals"]), 5)

    def test_justification_mentions_source(self):
        art = _make_article(source="Reuters")
        result = select_news_of_day([art])
        has_source = any("Reuters" in j for j in result["justification"])
        self.assertTrue(has_source)


if __name__ == "__main__":
    unittest.main()
