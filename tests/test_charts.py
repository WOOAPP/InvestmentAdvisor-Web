"""Tests for charts.py — helpers and edge cases.

charts.py imports TkAgg at module level.  We mock the Tk dependency chain
before importing so tests run in headless CI.
"""

import unittest
import sys, os
from unittest.mock import MagicMock

# ── Mock entire Tk dependency chain before any matplotlib backend import ──
_TK_MODS = [
    "tkinter", "tkinter.ttk", "tkinter.scrolledtext", "tkinter.messagebox",
    "tkinter.filedialog", "tkinter.simpledialog", "tkinter.font",
    "tkinter.colorchooser",
]
for mod in _TK_MODS:
    sys.modules.setdefault(mod, MagicMock())

# Mock backend_tkagg so charts.py import succeeds
_mock_canvas = MagicMock()
_mock_toolbar = MagicMock()
_backend_mock = MagicMock()
_backend_mock.FigureCanvasTkAgg = _mock_canvas
_backend_mock.NavigationToolbar2Tk = _mock_toolbar
sys.modules.setdefault(
    "matplotlib.backends.backend_tkagg", _backend_mock)
sys.modules.setdefault(
    "matplotlib.backends._backend_tk", MagicMock())

import matplotlib
matplotlib.use("Agg")

# Mock yfinance (not installed in CI)
sys.modules.setdefault("yfinance", MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np

from modules.charts import (
    _bar_width, _compute_vol_colors, _setup_xaxis,
    extract_risk_level, COLORS,
)


def _make_hist(n, freq="D"):
    """Create a synthetic OHLCV DataFrame with n rows."""
    idx = pd.date_range("2025-01-01", periods=n, freq=freq)
    rng = np.random.default_rng(42)
    close = pd.Series(rng.uniform(100, 200, n), index=idx, name="Close")
    open_ = close.shift(1).fillna(close)
    vol = pd.Series(rng.integers(1_000_000, 10_000_000, n), index=idx, name="Volume")
    return pd.DataFrame({"Open": open_, "Close": close, "Volume": vol})


class TestBarWidth(unittest.TestCase):

    def test_daily_data(self):
        hist = _make_hist(30, freq="D")
        w = _bar_width(hist)
        self.assertGreater(w, 0.5)
        self.assertLess(w, 1.5)

    def test_intraday_data(self):
        hist = _make_hist(100, freq="h")
        w = _bar_width(hist)
        self.assertLess(w, 0.1)
        self.assertGreater(w, 0.0)

    def test_single_row(self):
        hist = _make_hist(1)
        w = _bar_width(hist)
        self.assertEqual(w, 0.8)

    def test_two_rows(self):
        hist = _make_hist(2, freq="D")
        w = _bar_width(hist)
        self.assertGreater(w, 0)


class TestVolColors(unittest.TestCase):

    def test_green_when_close_above_open(self):
        hist = pd.DataFrame({"Open": [100.0], "Close": [110.0], "Volume": [1e6]})
        colors = _compute_vol_colors(hist)
        self.assertEqual(colors, [COLORS["green"]])

    def test_red_when_close_below_open(self):
        hist = pd.DataFrame({"Open": [110.0], "Close": [100.0], "Volume": [1e6]})
        colors = _compute_vol_colors(hist)
        self.assertEqual(colors, [COLORS["red"]])

    def test_handles_nan_without_crash(self):
        hist = pd.DataFrame({
            "Open": [100.0, float("nan")],
            "Close": [110.0, 105.0],
            "Volume": [1e6, 1e6],
        })
        colors = _compute_vol_colors(hist)
        self.assertEqual(len(colors), 2)

    def test_no_open_column(self):
        hist = pd.DataFrame({
            "Close": [100.0, 105.0, 103.0],
            "Volume": [1e6, 1e6, 1e6],
        })
        colors = _compute_vol_colors(hist)
        self.assertEqual(len(colors), 3)
        self.assertEqual(colors[0], COLORS["green"])   # first bar: close >= itself
        self.assertEqual(colors[1], COLORS["green"])   # 105 >= 100
        self.assertEqual(colors[2], COLORS["red"])     # 103 < 105

    def test_large_dataframe_vectorised(self):
        hist = _make_hist(500)
        colors = _compute_vol_colors(hist)
        self.assertEqual(len(colors), 500)


class TestSetupXaxis(unittest.TestCase):

    def test_all_periods_no_crash(self):
        """_setup_xaxis handles every period without error."""
        from matplotlib.figure import Figure
        for period in ("1T", "5T", "1M", "3M", "6M", "1R", "2R"):
            fig = Figure()
            ax = fig.add_subplot(111)
            hist = _make_hist(30)
            ax.plot(hist.index, hist["Close"])
            try:
                _setup_xaxis(ax, period, 30)
            except Exception as e:
                self.fail(f"_setup_xaxis crashed for period={period}: {e}")


class TestExtractRiskLevel(unittest.TestCase):

    def test_slash_format(self):
        self.assertEqual(extract_risk_level("Ryzyko: 7/10"), 7)

    def test_bold_markdown(self):
        self.assertEqual(extract_risk_level("ryzyko **8**/10"), 8)

    def test_out_of_range_ignored(self):
        self.assertEqual(extract_risk_level("Score: 15/10"), 5)

    def test_default(self):
        self.assertEqual(extract_risk_level("No risk mentioned"), 5)


if __name__ == "__main__":
    unittest.main()
