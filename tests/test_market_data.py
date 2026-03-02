"""Tests for market_data.py — yfinance, coingecko, stooq, FX cache, formatting."""

import unittest
import sys, os
from unittest.mock import patch, MagicMock
import types
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub yfinance before importing market_data (not installed in test env)
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = types.ModuleType("yfinance")

import modules.market_data as md


# ── Helper factories ───────────────────────────────────────────
def _mock_hist(closes, volumes=None):
    """Create a mock DataFrame resembling yfinance history."""
    n = len(closes)
    df = pd.DataFrame({
        "Close": closes,
        "Open": [c - 0.5 for c in closes],
        "High": [c + 1 for c in closes],
        "Low": [c - 1 for c in closes],
        "Volume": volumes if volumes is not None else [1000] * n,
    })
    return df


class TestGetYfinanceData(unittest.TestCase):

    @patch("modules.market_data.yf")
    def test_basic_return(self, mock_yf):
        ticker = MagicMock()
        ticker.history.return_value = _mock_hist([100.0, 101.0, 102.5])
        mock_yf.Ticker.return_value = ticker

        result = md.get_yfinance_data("AAPL", "Apple")
        self.assertEqual(result["name"], "Apple")
        self.assertAlmostEqual(result["price"], 102.5, places=2)
        self.assertAlmostEqual(result["change"], 1.5, places=2)
        self.assertEqual(result["source"], "yfinance")
        self.assertIn("sparkline", result)
        self.assertEqual(len(result["sparkline"]), 3)

    @patch("modules.market_data.yf")
    def test_empty_history(self, mock_yf):
        ticker = MagicMock()
        ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = ticker

        result = md.get_yfinance_data("BAD")
        self.assertIn("error", result)

    @patch("modules.market_data.yf")
    def test_nan_volume(self, mock_yf):
        ticker = MagicMock()
        ticker.history.return_value = _mock_hist(
            [50.0, 51.0], volumes=[np.nan, np.nan])
        mock_yf.Ticker.return_value = ticker

        result = md.get_yfinance_data("^GSPC", "S&P 500")
        self.assertEqual(result["volume"], 0)

    @patch("modules.market_data.yf")
    def test_single_close(self, mock_yf):
        ticker = MagicMock()
        ticker.history.return_value = _mock_hist([200.0])
        mock_yf.Ticker.return_value = ticker

        result = md.get_yfinance_data("SOLO")
        self.assertAlmostEqual(result["price"], 200.0)
        self.assertAlmostEqual(result["change"], 0.0)

    @patch("modules.market_data.yf")
    def test_exception_returns_error(self, mock_yf):
        import requests
        mock_yf.Ticker.side_effect = requests.ConnectionError("network timeout")

        result = md.get_yfinance_data("FAIL", "Fail Inc")
        self.assertIn("error", result)
        self.assertEqual(result["name"], "Fail Inc")
        self.assertIn("network timeout", result["error"])


class TestGetCoingeckoData(unittest.TestCase):

    @patch("modules.market_data.safe_get")
    def test_basic_return(self, mock_get):
        price_resp = MagicMock()
        price_resp.json.return_value = {
            "bitcoin": {
                "usd": 65000,
                "usd_24h_change": 2.5,
                "usd_24h_vol": 30_000_000_000,
            }
        }
        chart_resp = MagicMock()
        chart_resp.json.return_value = {
            "prices": [[1, 63000], [2, 64000], [3, 65000]]
        }
        mock_get.side_effect = [price_resp, chart_resp]

        result = md.get_coingecko_data("bitcoin", "Bitcoin")
        self.assertEqual(result["name"], "Bitcoin")
        self.assertEqual(result["price"], 65000)
        self.assertAlmostEqual(result["change_pct"], 2.5)
        self.assertEqual(result["source"], "coingecko")
        self.assertEqual(len(result["sparkline"]), 3)

    @patch("modules.market_data.safe_get")
    def test_missing_coin(self, mock_get):
        resp = MagicMock()
        resp.json.return_value = {}
        mock_get.return_value = resp

        result = md.get_coingecko_data("nonexistent")
        self.assertIn("error", result)

    @patch("modules.market_data.safe_get")
    def test_exception_returns_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("API limit")

        result = md.get_coingecko_data("bitcoin", "Bitcoin")
        self.assertIn("error", result)
        self.assertIn("API limit", result["error"])


class TestGetStooqData(unittest.TestCase):

    @patch("modules.market_data.safe_get")
    def test_basic_return(self, mock_get):
        resp = MagicMock()
        # stooq CSV: Symbol,Date,Time,Open,Low,High,Close,Volume
        resp.text = (
            "Symbol,Date,Time,Open,Low,High,Close,Volume\n"
            "WIG20,2025-01-02,16:00,2000.0,1980.0,2050.0,2040.0,50000"
        )
        mock_get.return_value = resp

        result = md.get_stooq_data("WIG20", "WIG20 (GPW)")
        self.assertEqual(result["name"], "WIG20 (GPW)")
        self.assertAlmostEqual(result["price"], 2040.0)
        self.assertEqual(result["source"], "stooq")

    @patch("modules.market_data.safe_get")
    def test_single_line(self, mock_get):
        resp = MagicMock()
        resp.text = "Header only"
        mock_get.return_value = resp

        result = md.get_stooq_data("BAD")
        self.assertIn("error", result)

    @patch("modules.market_data.safe_get")
    def test_short_csv_fields(self, mock_get):
        resp = MagicMock()
        resp.text = "H1,H2\nA,B,C"
        mock_get.return_value = resp

        result = md.get_stooq_data("SHORT")
        self.assertIn("error", result)


class TestGetFxToUsd(unittest.TestCase):

    def setUp(self):
        # Clear cache before each test
        md._fx_cache.clear()

    def test_usd_returns_one(self):
        self.assertEqual(md.get_fx_to_usd("USD"), 1.0)

    def test_usd_case_insensitive(self):
        self.assertEqual(md.get_fx_to_usd("usd"), 1.0)

    @patch("modules.market_data.yf")
    def test_pln_rate(self, mock_yf):
        ticker = MagicMock()
        ticker.history.return_value = _mock_hist([0.25, 0.26])
        mock_yf.Ticker.return_value = ticker

        rate = md.get_fx_to_usd("PLN")
        self.assertIsNotNone(rate)
        self.assertAlmostEqual(rate, 0.26)

    @patch("modules.market_data.yf")
    def test_cache_hit(self, mock_yf):
        ticker = MagicMock()
        ticker.history.return_value = _mock_hist([0.25])
        mock_yf.Ticker.return_value = ticker

        md.get_fx_to_usd("EUR")
        md.get_fx_to_usd("EUR")
        # Ticker called only once
        mock_yf.Ticker.assert_called_once()

    @patch("modules.market_data.yf")
    def test_empty_history_returns_none(self, mock_yf):
        ticker = MagicMock()
        ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = ticker

        self.assertIsNone(md.get_fx_to_usd("XYZ"))

    @patch("modules.market_data.yf")
    def test_exception_returns_none(self, mock_yf):
        import requests
        mock_yf.Ticker.side_effect = requests.ConnectionError("network")

        self.assertIsNone(md.get_fx_to_usd("GBP"))


class TestGetAllInstruments(unittest.TestCase):

    @patch("modules.market_data.get_stooq_data")
    @patch("modules.market_data.get_coingecko_data")
    @patch("modules.market_data.get_yfinance_data")
    def test_dispatches_by_source(self, mock_yf, mock_cg, mock_stq):
        mock_yf.return_value = {"name": "SPY", "price": 450}
        mock_cg.return_value = {"name": "BTC", "price": 65000}
        mock_stq.return_value = {"name": "WIG", "price": 2000}

        instruments = [
            {"symbol": "SPY", "name": "S&P 500", "source": "yfinance"},
            {"symbol": "bitcoin", "name": "Bitcoin", "source": "coingecko"},
            {"symbol": "WIG20", "name": "WIG20", "source": "stooq"},
        ]
        results = md.get_all_instruments(instruments)

        self.assertIn("SPY", results)
        self.assertIn("bitcoin", results)
        self.assertIn("WIG20", results)
        mock_yf.assert_called_once()
        mock_cg.assert_called_once()
        mock_stq.assert_called_once()

    def test_skips_empty_symbol(self):
        instruments = [{"symbol": "", "name": "Empty", "source": "yfinance"}]
        results = md.get_all_instruments(instruments)
        self.assertEqual(len(results), 0)


class TestFormatMarketSummary(unittest.TestCase):

    def test_categorizes_crypto(self):
        data = {"BTC-USD": {"name": "Bitcoin", "price": 65000,
                            "change_pct": 2.0, "source": "coingecko",
                            "high_5d": 66000, "low_5d": 62000}}
        text = md.format_market_summary(data)
        self.assertIn("Kryptowaluty", text)
        self.assertIn("Bitcoin", text)

    def test_categorizes_forex(self):
        data = {"EURUSD=X": {"name": "EUR/USD", "price": 1.08,
                             "change_pct": -0.1, "source": "yfinance",
                             "high_5d": 1.09, "low_5d": 1.07}}
        text = md.format_market_summary(data)
        self.assertIn("Forex", text)

    def test_categorizes_commodities(self):
        data = {"GC=F": {"name": "Gold", "price": 2000,
                         "change_pct": 0.5, "source": "yfinance",
                         "high_5d": 2010, "low_5d": 1990}}
        text = md.format_market_summary(data)
        self.assertIn("Surowce", text)

    def test_error_entries(self):
        data = {"FAIL": {"name": "Fail", "error": "timeout"}}
        text = md.format_market_summary(data)
        self.assertIn("timeout", text)

    def test_includes_header(self):
        text = md.format_market_summary({})
        self.assertIn("AKTUALNE DANE RYNKOWE", text)

    def test_arrow_direction(self):
        data = {
            "UP": {"name": "Up", "price": 10, "change_pct": 1.5,
                   "source": "yfinance"},
            "DOWN": {"name": "Down", "price": 10, "change_pct": -2.0,
                     "source": "yfinance"},
        }
        text = md.format_market_summary(data)
        # We just check both arrows appear
        self.assertIn("▲", text)
        self.assertIn("▼", text)

    def test_merges_crypto_data(self):
        market = {"SPY": {"name": "S&P", "price": 450, "change_pct": 0.1,
                          "source": "yfinance"}}
        crypto = {"BTC-USD": {"name": "BTC", "price": 65000,
                              "change_pct": 1.0, "source": "coingecko"}}
        text = md.format_market_summary(market, crypto)
        self.assertIn("S&P", text)
        self.assertIn("BTC", text)


if __name__ == "__main__":
    unittest.main()
