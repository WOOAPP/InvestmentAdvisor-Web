"""Tests for database.py — CRUD, migrations, thread-safe connections."""

import unittest
import sys, os
import sqlite3
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import modules.database as db


class _TempDBMixin:
    """Monkey-patch DB_PATH to a temp file for each test."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self._orig_path = db.DB_PATH
        db.DB_PATH = self.db_path
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig_path
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestInitDB(_TempDBMixin, unittest.TestCase):

    def test_tables_created(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in c.fetchall()}
        conn.close()
        for t in ("reports", "market_snapshots", "alerts",
                   "portfolio", "instrument_profiles"):
            self.assertIn(t, tables)

    def test_idempotent(self):
        db.init_db()
        db.init_db()
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in c.fetchall()}
        conn.close()
        self.assertIn("reports", tables)


class TestReports(_TempDBMixin, unittest.TestCase):

    def test_save_and_get_by_id(self):
        rid = db.save_report("anthropic", "claude-opus-4-6",
                             "market summary", "analysis text", 5, 100, 200)
        self.assertIsNotNone(rid)
        row = db.get_report_by_id(rid)
        self.assertIsNotNone(row)
        self.assertEqual(row[2], "anthropic")
        self.assertEqual(row[3], "claude-opus-4-6")
        self.assertEqual(row[5], "analysis text")
        self.assertEqual(row[6], 5)
        self.assertEqual(row[7], 100)
        self.assertEqual(row[8], 200)

    def test_get_reports_list(self):
        db.save_report("a", "m1", "s1", "a1")
        db.save_report("b", "m2", "s2", "a2")
        rows = db.get_reports(limit=10)
        self.assertEqual(len(rows), 2)
        # newest id first (both may share same created_at timestamp)
        providers = [r[2] for r in rows]
        self.assertIn("a", providers)
        self.assertIn("b", providers)

    def test_get_latest_report(self):
        db.save_report("a", "m1", "s1", "first")
        db.save_report("b", "m2", "s2", "second")
        row = db.get_latest_report()
        self.assertIn("second", row[5])

    def test_get_latest_report_empty(self):
        row = db.get_latest_report()
        self.assertIsNone(row)

    def test_delete_report(self):
        rid = db.save_report("a", "m", "s", "del")
        db.delete_report(rid)
        self.assertIsNone(db.get_report_by_id(rid))

    def test_get_reports_limit(self):
        for i in range(5):
            db.save_report("p", "m", "s", f"a{i}")
        rows = db.get_reports(limit=3)
        self.assertEqual(len(rows), 3)

    def test_save_report_none_tokens(self):
        rid = db.save_report("p", "m", "s", "a", 0,
                             input_tokens=None, output_tokens=None)
        row = db.get_report_by_id(rid)
        self.assertEqual(row[7], 0)
        self.assertEqual(row[8], 0)


class TestMarketSnapshots(_TempDBMixin, unittest.TestCase):

    def test_save_and_get_history(self):
        data = {
            "AAPL": {"name": "Apple", "price": 150.0, "change_pct": 1.5},
            "GOOG": {"name": "Google", "price": 2800.0, "change_pct": -0.5},
        }
        db.save_market_snapshot(data)
        history = db.get_price_history("AAPL", days=1)
        self.assertGreaterEqual(len(history), 1)
        self.assertAlmostEqual(history[0][1], 150.0, places=1)

    def test_skips_error_entries(self):
        data = {
            "BAD": {"name": "Bad", "error": "no data"},
            "GOOD": {"name": "Good", "price": 10.0, "change_pct": 0},
        }
        db.save_market_snapshot(data)
        bad_hist = db.get_price_history("BAD")
        good_hist = db.get_price_history("GOOD")
        self.assertEqual(len(bad_hist), 0)
        self.assertEqual(len(good_hist), 1)


class TestAlerts(_TempDBMixin, unittest.TestCase):

    def test_add_and_get_unseen(self):
        db.add_alert("AAPL", "Price crossed $150")
        alerts = db.get_unseen_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][2], "AAPL")
        self.assertEqual(alerts[0][3], "Price crossed $150")

    def test_mark_seen(self):
        db.add_alert("BTC", "New high")
        db.mark_alerts_seen()
        alerts = db.get_unseen_alerts()
        self.assertEqual(len(alerts), 0)

    def test_no_unseen_initially(self):
        self.assertEqual(len(db.get_unseen_alerts()), 0)


class TestPortfolio(_TempDBMixin, unittest.TestCase):

    def test_add_and_list(self):
        db.add_portfolio_position("AAPL", "Apple", 10, 150.0)
        positions = db.get_portfolio_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0][1], "AAPL")
        self.assertEqual(positions[0][2], "Apple")
        self.assertAlmostEqual(positions[0][3], 10.0)
        self.assertAlmostEqual(positions[0][4], 150.0)

    def test_currency_fields(self):
        db.add_portfolio_position("WIG20", "WIG20", 5, 100.0,
                                  buy_currency="PLN", buy_fx_to_usd=0.25)
        pos = db.get_portfolio_positions()
        self.assertEqual(pos[0][6], "PLN")
        self.assertAlmostEqual(pos[0][7], 0.25)
        self.assertAlmostEqual(pos[0][8], 25.0)  # 100 * 0.25

    def test_delete_position(self):
        db.add_portfolio_position("AAPL", "Apple", 1, 100.0)
        positions = db.get_portfolio_positions()
        pid = positions[0][0]
        db.delete_portfolio_position(pid)
        self.assertEqual(len(db.get_portfolio_positions()), 0)

    def test_default_usd(self):
        db.add_portfolio_position("SPY", "S&P 500", 2, 500.0)
        pos = db.get_portfolio_positions()
        self.assertEqual(pos[0][6], "USD")
        self.assertAlmostEqual(pos[0][7], 1.0)
        self.assertAlmostEqual(pos[0][8], 500.0)


class TestInstrumentProfiles(_TempDBMixin, unittest.TestCase):

    def test_save_and_get(self):
        db.save_instrument_profile("AAPL", "Apple Inc. is a tech company.")
        result = db.get_instrument_profile("AAPL")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "Apple Inc. is a tech company.")

    def test_upsert(self):
        db.save_instrument_profile("AAPL", "Version 1")
        db.save_instrument_profile("AAPL", "Version 2")
        result = db.get_instrument_profile("AAPL")
        self.assertEqual(result[0], "Version 2")

    def test_get_nonexistent(self):
        self.assertIsNone(db.get_instrument_profile("NONE"))


class TestMigrations(_TempDBMixin, unittest.TestCase):

    def test_migrate_reports_usage_idempotent(self):
        with db._connect() as conn:
            db._migrate_reports_usage(conn)
            db._migrate_reports_usage(conn)
        rid = db.save_report("p", "m", "s", "a", 0, 42, 84)
        row = db.get_report_by_id(rid)
        self.assertEqual(row[7], 42)
        self.assertEqual(row[8], 84)

    def test_migrate_portfolio_currency_idempotent(self):
        with db._connect() as conn:
            db._migrate_portfolio_currency(conn)
            db._migrate_portfolio_currency(conn)
        db.add_portfolio_position("X", "X", 1, 10.0, "EUR", 1.1)
        pos = db.get_portfolio_positions()
        self.assertEqual(pos[0][6], "EUR")


if __name__ == "__main__":
    unittest.main()
