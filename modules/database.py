import sqlite3
import json
import os
from datetime import datetime

DB_PATH = "data/advisor.db"

def _migrate_reports_usage(conn):
    """Add usage columns to reports table if missing (backward-compat migration)."""
    c = conn.cursor()
    existing = {row[1] for row in c.execute("PRAGMA table_info(reports)").fetchall()}
    for col, coltype, default in [
        ("input_tokens", "INTEGER", "0"),
        ("output_tokens", "INTEGER", "0"),
    ]:
        if col not in existing:
            c.execute(f"ALTER TABLE reports ADD COLUMN {col} {coltype} DEFAULT {default}")
    conn.commit()


def init_db():
    """Tworzy tabele jeśli nie istnieją."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            market_summary TEXT,
            analysis TEXT,
            risk_level INTEGER,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            price REAL,
            change_pct REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            symbol TEXT,
            message TEXT,
            seen INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            name TEXT,
            quantity REAL NOT NULL,
            buy_price REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS instrument_profiles (
            symbol TEXT PRIMARY KEY,
            profile_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    _migrate_reports_usage(conn)
    conn.close()

def save_report(provider, model, market_summary, analysis, risk_level=0,
                input_tokens=0, output_tokens=0):
    """Zapisuje raport do bazy."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO reports
            (created_at, provider, model, market_summary, analysis,
             risk_level, input_tokens, output_tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), provider, model,
          market_summary, analysis, risk_level,
          int(input_tokens or 0), int(output_tokens or 0)))
    report_id = c.lastrowid
    conn.commit()
    conn.close()
    return report_id

def get_reports(limit=50):
    """Zwraca listę raportów (najnowsze pierwsze)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, created_at, provider, model, risk_level,
               substr(analysis, 1, 200) as preview
        FROM reports ORDER BY created_at DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_report_by_id(report_id):
    """Zwraca pełny raport po ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_latest_report():
    """Zwraca najnowszy raport (po id malejąco) lub None."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row

def save_market_snapshot(market_data):
    """Zapisuje snapshot cen rynkowych."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for symbol, d in market_data.items():
        if "error" not in d:
            c.execute("""
                INSERT INTO market_snapshots (created_at, symbol, name, price, change_pct)
                VALUES (?, ?, ?, ?, ?)
            """, (now, symbol, d.get("name", symbol), d.get("price", 0), d.get("change_pct", 0)))
    conn.commit()
    conn.close()

def get_price_history(symbol, days=30):
    """Zwraca historię cen dla wykresu."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT created_at, price FROM market_snapshots
        WHERE symbol = ?
        ORDER BY created_at DESC LIMIT ?
    """, (symbol, days * 10))
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))

def add_alert(symbol, message):
    """Dodaje alert."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO alerts (created_at, symbol, message)
        VALUES (?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, message))
    conn.commit()
    conn.close()

def get_unseen_alerts():
    """Zwraca nieprzeczytane alerty."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, created_at, symbol, message FROM alerts WHERE seen = 0 ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def mark_alerts_seen():
    """Oznacza wszystkie alerty jako przeczytane."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE alerts SET seen = 1 WHERE seen = 0")
    conn.commit()
    conn.close()

def delete_report(report_id):
    """Usuwa raport po ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()

# ── PORTFOLIO ──

def add_portfolio_position(symbol, name, quantity, buy_price):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO portfolio (symbol, name, quantity, buy_price, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (symbol, name or symbol, float(quantity), float(buy_price),
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_portfolio_positions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, symbol, name, quantity, buy_price, created_at
        FROM portfolio ORDER BY created_at
    """)
    rows = c.fetchall()
    conn.close()
    return rows

def delete_portfolio_position(position_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM portfolio WHERE id = ?", (position_id,))
    conn.commit()
    conn.close()

# ── INSTRUMENT PROFILES ──

def get_instrument_profile(symbol):
    """Zwraca (profile_text, created_at) lub None."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT profile_text, created_at FROM instrument_profiles WHERE symbol = ?",
        (symbol,))
    row = c.fetchone()
    conn.close()
    return row


def save_instrument_profile(symbol, profile_text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO instrument_profiles (symbol, profile_text, created_at)
        VALUES (?, ?, ?)
    """, (symbol, profile_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


# Inicjalizacja przy imporcie
init_db()