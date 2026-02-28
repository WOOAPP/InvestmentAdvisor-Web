import yfinance as yf
import requests
from datetime import datetime
import pandas as pd

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── YAHOO FINANCE ──
def get_yfinance_data(symbol, name=""):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if hist.empty:
            return {"name": name or symbol, "error": "brak danych"}
        current = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2] if len(hist) >= 2 else current
        change = current - prev
        change_pct = (change / prev) * 100 if prev != 0 else 0
        return {
            "name": name or symbol,
            "price": round(current, 4),
            "change": round(change, 4),
            "change_pct": round(change_pct, 2),
            "volume": int(hist["Volume"].iloc[-1]) if "Volume" in hist else 0,
            "high_5d": round(hist["Close"].max(), 4),
            "low_5d": round(hist["Close"].min(), 4),
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
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json().get(coin_id, {})
        if not data:
            return {"name": name or coin_id, "error": "brak danych CoinGecko"}
        return {
            "name": name or coin_id,
            "price": data.get("usd", 0),
            "change_pct": round(data.get("usd_24h_change", 0), 2),
            "volume": data.get("usd_24h_vol", 0),
            "change": 0,
            "high_5d": 0,
            "low_5d": 0,
            "source": "coingecko",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    except Exception as e:
        return {"name": name or coin_id, "error": str(e)}

# ── STOOQ ──
def get_stooq_data(symbol, name=""):
    try:
        url = f"https://stooq.pl/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
        r = requests.get(url, headers=HEADERS, timeout=10)
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

def get_crypto_data(coins=["bitcoin", "ethereum"]):
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
        r = requests.get(url, timeout=10)
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