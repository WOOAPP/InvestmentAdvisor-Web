import yfinance as yf
from datetime import datetime
import logging
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_api_key
from modules.http_client import safe_get

logger = logging.getLogger(__name__)

# ── YAHOO FINANCE ──
def get_yfinance_data(symbol, name=""):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if hist.empty:
            return {"name": name or symbol, "error": "brak danych"}

        # Robust conversion - handle NaN, strings, and non-numeric values
        closes = pd.to_numeric(hist["Close"], errors="coerce").dropna()
        if closes.empty:
            return {"name": name or symbol, "error": "brak danych cenowych"}

        current = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) >= 2 else current
        change = current - prev
        change_pct = (change / prev) * 100 if prev != 0 else 0

        # Handle volume safely (indices often have NaN volume)
        vol = 0
        if "Volume" in hist.columns:
            last_vol = hist["Volume"].iloc[-1]
            if pd.notna(last_vol):
                try:
                    vol = int(float(last_vol))
                except (ValueError, TypeError):
                    vol = 0

        sparkline = []
        for v in closes.tolist():
            try:
                sparkline.append(round(float(v), 4))
            except (ValueError, TypeError):
                pass

        return {
            "name": name or symbol,
            "price": round(current, 4),
            "change": round(change, 4),
            "change_pct": round(change_pct, 2),
            "volume": vol,
            "high_5d": round(float(closes.max()), 4),
            "low_5d": round(float(closes.min()), 4),
            "sparkline": sparkline,
            "source": "yfinance",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    except Exception as e:
        return {"name": name or symbol, "error": str(e)}

# ── COINGECKO ──
def get_coingecko_data(coin_id, name=""):
    try:
        url = (f"https://api.coingecko.com/api/v3/simple/price"
               f"?ids={coin_id}&vs_currencies=usd"
               f"&include_24hr_change=true&include_24hr_vol=true")
        r = safe_get(url)
        data = r.json().get(coin_id, {})
        if not data:
            return {"name": name or coin_id, "error": "brak danych CoinGecko"}
        sparkline = []
        try:
            chart_url = (f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                         f"/market_chart?vs_currency=usd&days=5&interval=daily")
            cr = safe_get(chart_url)
            sparkline = [round(p[1], 4) for p in cr.json().get("prices", [])]
        except Exception:
            pass

        price = data.get("usd", 0)
        change_pct = round(data.get("usd_24h_change", 0), 2)

        # Calculate change, high_5d, low_5d from sparkline data
        change = 0
        high_5d = 0
        low_5d = 0
        if sparkline:
            high_5d = max(sparkline)
            low_5d = min(sparkline)
            if len(sparkline) >= 2:
                change = round(sparkline[-1] - sparkline[-2], 4)

        return {
            "name": name or coin_id,
            "price": price,
            "change_pct": change_pct,
            "volume": data.get("usd_24h_vol", 0),
            "change": change,
            "high_5d": high_5d,
            "low_5d": low_5d,
            "sparkline": sparkline,
            "source": "coingecko",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    except Exception as e:
        return {"name": name or coin_id, "error": str(e)}

# ── STOOQ ──
def get_stooq_data(symbol, name=""):
    try:
        url = f"https://stooq.pl/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
        r = safe_get(url)
        lines = r.text.strip().split("\n")
        if len(lines) < 2:
            return {"name": name or symbol, "error": "brak danych Stooq"}
        parts = lines[1].split(",")
        if len(parts) < 7:
            return {"name": name or symbol, "error": "błędny format Stooq"}
        close = float(parts[6])
        open_ = float(parts[3])
        change_pct = ((close - open_) / open_) * 100 if open_ != 0 else 0
        return {
            "name": name or symbol,
            "price": round(close, 4),
            "change": round(close - open_, 4),
            "change_pct": round(change_pct, 2),
            "volume": int(float(parts[7])) if len(parts) > 7 else 0,
            "high_5d": round(float(parts[5]), 4),
            "low_5d": round(float(parts[4]), 4),
            "sparkline": [round(open_, 4), round(close, 4)],
            "source": "stooq",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    except Exception as e:
        return {"name": name or symbol, "error": str(e)}

# ── POBIERZ WSZYSTKIE INSTRUMENTY ──
def get_all_instruments(instruments_config):
    """
    instruments_config to lista słowników:
    [{"symbol": "BTC-USD", "name": "Bitcoin", "category": "crypto", "source": "coingecko"}, ...]
    """
    results = {}
    for inst in instruments_config:
        symbol = inst.get("symbol", "")
        name = inst.get("name", symbol)
        source = inst.get("source", "yfinance")
        if not symbol:
            continue
        if source == "coingecko":
            results[symbol] = get_coingecko_data(symbol.lower(), name)
        elif source == "stooq":
            results[symbol] = get_stooq_data(symbol, name)
        else:
            results[symbol] = get_yfinance_data(symbol, name)
    return results

# ── LEGACY (zachowane dla kompatybilności) ──
def get_market_data(symbols):
    results = {}
    for s in symbols:
        results[s] = get_yfinance_data(s)
    return results

def get_crypto_data(coins=None):
    if coins is None:
        coins = ["bitcoin", "ethereum"]
    results = {}
    sym_map = {"bitcoin": "BTC-USD", "ethereum": "ETH-USD"}
    for coin in coins:
        results[sym_map.get(coin, coin)] = get_coingecko_data(coin, coin.capitalize())
    return results

def get_news(api_key, query="economy geopolitics markets", language="pl", page_size=10):
    if not api_key:
        return []
    try:
        url = (f"https://newsapi.org/v2/everything?"
               f"q={query}&language={language}&sortBy=publishedAt"
               f"&pageSize={page_size}&apiKey={api_key}")
        r = safe_get(url)
        data = r.json()
        return [
            {
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "source": a.get("source", {}).get("name", ""),
                "url": a.get("url", ""),
                "published": a.get("publishedAt", "")
            }
            for a in data.get("articles", []) if a.get("title")
        ]
    except Exception as e:
        logger.error("Błąd pobierania newsów: %s", e)
        return [{"error": str(e)}]

def format_market_summary(market_data, crypto_data=None):
    """Formatuje dane rynkowe do tekstu dla AI."""
    all_data = {**market_data}
    if crypto_data:
        all_data.update(crypto_data)

    categories = {
        "📈 Akcje / Indeksy": [],
        "🪙 Kryptowaluty": [],
        "💱 Forex": [],
        "🛢️ Surowce": [],
        "📊 Inne": []
    }

    for symbol, d in all_data.items():
        if "error" in d:
            line = f"{d.get('name', symbol)}: błąd - {d['error']}"
        else:
            arrow = "▲" if d.get("change_pct", 0) >= 0 else "▼"
            line = (f"{d.get('name', symbol)}: {d.get('price', 0)} "
                    f"{arrow} {d.get('change_pct', 0):+.2f}%")
            if d.get("high_5d") and d.get("low_5d"):
                line += f" (5d H:{d['high_5d']} L:{d['low_5d']})"

        src = d.get("source", "yfinance")
        if src == "coingecko" or "BTC" in symbol or "ETH" in symbol:
            categories["🪙 Kryptowaluty"].append(line)
        elif any(x in symbol for x in ["=X", "PLN", "EUR", "USD", "GBP"]):
            categories["💱 Forex"].append(line)
        elif any(x in symbol for x in ["=F", "GC", "CL", "SI", "KC", "CC"]):
            categories["🛢️ Surowce"].append(line)
        elif any(x in symbol for x in ["SPY", "QQQ", "WIG", "DAX", "N225", "FTSE", "^"]):
            categories["📈 Akcje / Indeksy"].append(line)
        else:
            categories["📊 Inne"].append(line)

    lines = ["=== AKTUALNE DANE RYNKOWE ===\n"]
    for cat, items in categories.items():
        if items:
            lines.append(f"\n{cat}")
            lines.extend(items)
    return "\n".join(lines)
