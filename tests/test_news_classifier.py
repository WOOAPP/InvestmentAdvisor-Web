"""Tests for C3: deterministic region + topic classification."""

import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.news_classifier import (
    classify_region, classify_topic, classify_article, classify_articles,
)


class TestRegionClassification(unittest.TestCase):

    def test_polska_by_keyword(self):
        self.assertEqual(classify_region("NBP podnosi stopy procentowe"), "Polska")

    def test_polska_by_wig(self):
        self.assertEqual(classify_region("WIG20 hits record high"), "Polska")

    def test_europa_by_ecb(self):
        self.assertEqual(classify_region("ECB raises rates again"), "Europa")

    def test_europa_by_country(self):
        self.assertEqual(classify_region("Germany enters recession"), "Europa")

    def test_europa_dax(self):
        self.assertEqual(classify_region("DAX drops 3% on trade fears"), "Europa")

    def test_ameryka_by_fed(self):
        self.assertEqual(classify_region("Fed holds rates steady"), "Ameryka Pn.")

    def test_ameryka_by_wall_street(self):
        self.assertEqual(classify_region("Wall Street rallies on earnings"), "Ameryka Pn.")

    def test_ameryka_sp500(self):
        self.assertEqual(classify_region("S&P 500 reaches all-time high"), "Ameryka Pn.")

    def test_azja_by_china(self):
        self.assertEqual(classify_region("China GDP growth slows"), "Azja")

    def test_azja_by_nikkei(self):
        self.assertEqual(classify_region("Nikkei surges on BOJ intervention"), "Azja")

    def test_australia(self):
        self.assertEqual(classify_region("RBA cuts rates for third time"), "Australia")

    def test_australia_asx(self):
        self.assertEqual(classify_region("ASX gains on mining stocks"), "Australia")

    def test_default_swiat(self):
        self.assertEqual(classify_region("Global markets mixed"), "Świat")

    def test_description_fallback(self):
        # Title has no region signal, but description does
        self.assertEqual(
            classify_region("Rate decision today", "The ECB is expected to raise"),
            "Europa")

    def test_polska_priority_over_europa(self):
        # Polska mentions should beat Europa even with EU context
        self.assertEqual(
            classify_region("Poland GDP outperforms EU average"),
            "Polska")


class TestTopicClassification(unittest.TestCase):

    def test_banki_centralne(self):
        self.assertEqual(classify_topic("Fed raises interest rate by 25bp"), "banki centralne")

    def test_inflacja(self):
        self.assertEqual(classify_topic("CPI rises above expectations"), "inflacja/stopy")

    def test_konflikt(self):
        self.assertEqual(classify_topic("Russia escalates military operations in Ukraine"), "konflikt")

    def test_handel(self):
        self.assertEqual(classify_topic("New tariffs imposed on Chinese imports"), "handel")

    def test_tech_ai(self):
        self.assertEqual(classify_topic("NVIDIA reports record AI chip sales"), "tech/AI")

    def test_energia(self):
        self.assertEqual(classify_topic("OPEC cuts oil production"), "energia")

    def test_makro(self):
        self.assertEqual(classify_topic("GDP growth disappoints in Q3"), "makro")

    def test_rynek_pracy(self):
        self.assertEqual(classify_topic("Non-farm payrolls beat expectations"), "rynek pracy")

    def test_krypto(self):
        self.assertEqual(classify_topic("Bitcoin halving approaches"), "krypto")

    def test_surowce(self):
        self.assertEqual(classify_topic("Gold price hits all-time high"), "surowce")

    def test_nieruchomosci(self):
        self.assertEqual(classify_topic("Housing market cools as mortgage rates rise"), "nieruchomości")

    def test_default_inne(self):
        self.assertEqual(classify_topic("Weather forecast for next week"), "inne")


class TestClassifyArticle(unittest.TestCase):

    def test_adds_both_fields(self):
        art = {"title": "Fed cuts rates", "description": "The Federal Reserve"}
        result = classify_article(art)
        self.assertEqual(result["region"], "Ameryka Pn.")
        self.assertEqual(result["topic"], "banki centralne")
        # Should modify in-place
        self.assertIs(result, art)

    def test_classify_articles_batch(self):
        articles = [
            {"title": "ECB holds rates", "description": ""},
            {"title": "Bitcoin soars past 100k", "description": ""},
        ]
        result = classify_articles(articles)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["region"], "Europa")
        self.assertEqual(result[0]["topic"], "banki centralne")
        self.assertEqual(result[1]["topic"], "krypto")


if __name__ == "__main__":
    unittest.main()
