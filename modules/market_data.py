import yfinance as yf
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import threading as _threading
import time as _time
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_api_key
from modules.http_client import safe_get
from constants import (
    FX_CACHE_TTL, YFINANCE_HISTORY_PERIOD,
    PRICE_ROUND_DECIMALS, CHANGE_PCT_ROUND_DECIMALS,
    NEWS_DEFAULT_PAGE_SIZE,
)

# ── COINGECKO CACHE ──
_CG_PRICE_TTL      = 600   # 10 min — free tier ~30 req/min, nie bijemy zbyt często
_CG_SPARKLINE_TTL  = 3600  # 1 h  — sparkline zmienia się wolno (interwał dzienny)
_cg_price_cache     = {}   # {coin_id: (data_dict, ts)}
_cg_sparkline_cache = {}   # {coin_id: (list,      ts)}
_cg_lock            = _threading.Lock()

# ── COINGECKO RATE LIMITER ──
# Free tier: ~30 req/min = 1 req/2s. Używamy 2.5s marginesu bezpieczeństwa.
_CG_MIN_INTERVAL    = 2.5  # sekundy między requestami do CoinGecko
_cg_last_req_ts     = 0.0
_cg_req_lock        = _threading.Lock()


def _cg_rate_wait():
    """Serializuje requesty do CoinGecko i pilnuje minimalnego odstępu."""
    global _cg_last_req_ts
    with _cg_req_lock:
        now = _time.time()
        wait = _CG_MIN_INTERVAL - (now - _cg_last_req_ts)
        if wait > 0:
            _time.sleep(wait)
        _cg_last_req_ts = _time.time()

logger = logging.getLogger(__name__)

# ── YAHOO FINANCE ──
def get_yfinance_data(symbol, name=""):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=YFINANCE_HISTORY_PERIOD)
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
                sparkline.append(round(float(v), PRICE_ROUND_DECIMALS))
            except (ValueError, TypeError):
                pass

        return {
            "name": name or symbol,
            "price": round(current, PRICE_ROUND_DECIMALS),
            "change": round(change, PRICE_ROUND_DECIMALS),
            "change_pct": round(change_pct, CHANGE_PCT_ROUND_DECIMALS),
            "volume": vol,
            "high_5d": round(float(closes.max()), PRICE_ROUND_DECIMALS),
            "low_5d": round(float(closes.min()), PRICE_ROUND_DECIMALS),
            "sparkline": sparkline,
            "source": "yfinance",
            "timestamp": datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M")
        }
    except (requests.RequestException, KeyError, ValueError, TypeError) as e:
        logger.warning("yfinance %s failed: %s", symbol, e)
        return {"name": name or symbol, "error": str(e)}

# ── COINGECKO ──
def _cg_fetch_prices_batch(coin_ids):
    """Pobiera ceny wielu monet jednym żądaniem do CoinGecko.

    Zwraca dict {coin_id: {usd, usd_24h_change, usd_24h_vol}} lub {} przy błędzie.
    Wyniki trafiają do _cg_price_cache.
    """
    _cg_rate_wait()
    ids_str = ",".join(coin_ids)
    url = (f"https://api.coingecko.com/api/v3/simple/price"
           f"?ids={ids_str}&vs_currencies=usd"
           f"&include_24hr_change=true&include_24hr_vol=true")
    r = safe_get(url)
    batch = r.json()
    ts = _time.time()
    with _cg_lock:
        for cid, data in batch.items():
            _cg_price_cache[cid] = (data, ts)
    return batch


def _cg_get_sparkline(coin_id):
    """Zwraca sparkline z cache lub pobiera (TTL 1 h)."""
    with _cg_lock:
        cached = _cg_sparkline_cache.get(coin_id)
    if cached and (_time.time() - cached[1]) < _CG_SPARKLINE_TTL:
        return cached[0]
    try:
        _cg_rate_wait()
        chart_url = (f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                     f"/market_chart?vs_currency=usd&days=5&interval=daily")
        cr = safe_get(chart_url)
        sparkline = [round(p[1], PRICE_ROUND_DECIMALS)
                     for p in cr.json().get("prices", [])]
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.debug("CoinGecko sparkline for %s unavailable: %s", coin_id, e)
        sparkline = []
    with _cg_lock:
        _cg_sparkline_cache[coin_id] = (sparkline, _time.time())
    return sparkline


def _cg_build_result(coin_id, name, data, sparkline):
    """Buduje dict wyniku z surowych danych CoinGecko."""
    price = data.get("usd", 0)
    change_pct = round(data.get("usd_24h_change", 0), CHANGE_PCT_ROUND_DECIMALS)
    change = high_5d = low_5d = 0
    if sparkline:
        high_5d = max(sparkline)
        low_5d = min(sparkline)
        if len(sparkline) >= 2:
            change = round(sparkline[-1] - sparkline[-2], PRICE_ROUND_DECIMALS)
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
        "timestamp": datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M"),
    }


def get_coingecko_data(coin_id, name=""):
    """Pobiera dane jednej monety (z cache lub przez batch-fetch)."""
    with _cg_lock:
        cached = _cg_price_cache.get(coin_id)
    if cached and (_time.time() - cached[1]) < _CG_PRICE_TTL:
        data = cached[0]
    else:
        try:
            batch = _cg_fetch_prices_batch([coin_id])
            data = batch.get(coin_id, {})
        except (requests.RequestException, KeyError, ValueError, TypeError) as e:
            logger.warning("CoinGecko %s failed: %s", coin_id, e)
            return {"name": name or coin_id, "error": str(e)}
    if not data:
        return {"name": name or coin_id, "error": "brak danych CoinGecko"}
    sparkline = _cg_get_sparkline(coin_id)
    return _cg_build_result(coin_id, name, data, sparkline)

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
            "price": round(close, PRICE_ROUND_DECIMALS),
            "change": round(close - open_, PRICE_ROUND_DECIMALS),
            "change_pct": round(change_pct, CHANGE_PCT_ROUND_DECIMALS),
            "volume": int(float(parts[7])) if len(parts) > 7 else 0,
            "high_5d": round(float(parts[5]), PRICE_ROUND_DECIMALS),
            "low_5d": round(float(parts[4]), PRICE_ROUND_DECIMALS),
            "sparkline": [round(open_, PRICE_ROUND_DECIMALS), round(close, PRICE_ROUND_DECIMALS)],
            "source": "stooq",
            "timestamp": datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M")
        }
    except (requests.RequestException, ValueError, IndexError) as e:
        logger.warning("Stooq %s failed: %s", symbol, e)
        return {"name": name or symbol, "error": str(e)}

# ── FX RATES CACHE ──
_fx_cache = {}       # {"PLNUSD": (rate, timestamp), ...}
_fx_lock = _threading.Lock()
_FX_CACHE_TTL = FX_CACHE_TTL

def get_fx_to_usd(currency):
    """Return the multiplier that converts *currency* → USD.

    E.g. for PLN it returns ~0.25 (1 PLN = 0.25 USD).
    USD returns 1.0 immediately.  On failure returns None.
    """
    currency = currency.upper()
    if currency == "USD":
        return 1.0

    cache_key = f"{currency}USD"
    with _fx_lock:
        cached = _fx_cache.get(cache_key)
        if cached and (_time.time() - cached[1]) < _FX_CACHE_TTL:
            return cached[0]

    # yfinance ticker format: PLNUSD=X, EURUSD=X
    ticker_symbol = f"{currency}USD=X"
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=YFINANCE_HISTORY_PERIOD)
        if hist.empty:
            return None
        closes = pd.to_numeric(hist["Close"], errors="coerce").dropna()
        if closes.empty:
            return None
        rate = float(closes.iloc[-1])
        with _fx_lock:
            _fx_cache[cache_key] = (rate, _time.time())
        return rate
    except (requests.RequestException, KeyError, ValueError, TypeError) as e:
        logger.warning("FX fetch %s failed: %s", ticker_symbol, e)
        return None


# ── POBIERZ WSZYSTKIE INSTRUMENTY ──
def get_all_instruments(instruments_config):
    """
    instruments_config to lista słowników:
    [{"symbol": "BTC-USD", "name": "Bitcoin", "category": "crypto", "source": "coingecko"}, ...]

    Instrumenty CoinGecko są pobierane jednym zbiorczym żądaniem (batch),
    co drastycznie redukuje liczbę requestów i ryzyko 429.
    """
    results = {}
    cg_pending = []   # [(symbol, coin_id, name), ...]

    for inst in instruments_config:
        symbol = inst.get("symbol", "")
        name = inst.get("name", symbol)
        source = inst.get("source", "yfinance")
        if not symbol:
            continue
        if source == "coingecko":
            cg_pending.append((symbol, symbol.lower(), name))
        elif source == "stooq":
            results[symbol] = get_stooq_data(symbol, name)
        else:
            results[symbol] = get_yfinance_data(symbol, name)

    # ── Batch-fetch wszystkich CoinGecko monet jednym requestem ──
    if cg_pending:
        # Pomiń monety, których cache jest aktualny
        to_fetch = []
        now = _time.time()
        with _cg_lock:
            for _, coin_id, _ in cg_pending:
                cached = _cg_price_cache.get(coin_id)
                if not (cached and (now - cached[1]) < _CG_PRICE_TTL):
                    to_fetch.append(coin_id)

        if to_fetch:
            try:
                _cg_fetch_prices_batch(to_fetch)
            except (requests.RequestException, KeyError, ValueError, TypeError) as e:
                logger.warning("CoinGecko batch failed: %s", e)

        # Zbuduj wyniki z cache (wypełnionego przez batch lub wcześniej)
        for symbol, coin_id, name in cg_pending:
            with _cg_lock:
                cached = _cg_price_cache.get(coin_id)
            if cached:
                sparkline = _cg_get_sparkline(coin_id)
                results[symbol] = _cg_build_result(coin_id, name, cached[0], sparkline)
            else:
                results[symbol] = {"name": name, "error": "brak danych CoinGecko"}

    return results

# ── SPARKLINE PO PRZEDZIALE CZASOWYM ──
_SPARK_CFG = {
    "1m":  {"yf_period": "1d",  "yf_interval": "1m",  "cg_days": "1"},
    "15m": {"yf_period": "5d",  "yf_interval": "15m", "cg_days": "1"},
    "1h":  {"yf_period": "5d",  "yf_interval": "1h",  "cg_days": "1"},
    "6h":  {"yf_period": "30d", "yf_interval": "1h",  "cg_days": "7"},
    "24h": {"yf_period": "60d", "yf_interval": "1d",  "cg_days": "30"},
}

def get_sparkline_by_timeframe(symbol, timeframe, source="yfinance"):
    """Zwraca listę cen (sparkline) dla danego przedziału czasowego.

    source: 'yfinance', 'coingecko', 'stooq'
    timeframe: '1m', '15m', '1h', '6h', '24h'
    """
    cfg = _SPARK_CFG.get(timeframe, _SPARK_CFG["1h"])
    try:
        if source == "coingecko":
            _cg_rate_wait()
            coin_id = symbol.lower()
            url = (f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                   f"/market_chart?vs_currency=usd&days={cfg['cg_days']}")
            r = safe_get(url)
            return [round(float(p[1]), PRICE_ROUND_DECIMALS)
                    for p in r.json().get("prices", [])]
        elif source == "stooq":
            return []   # stooq nie wspiera danych intraday
        else:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=cfg["yf_period"], interval=cfg["yf_interval"])
            if hist.empty:
                return []
            closes = pd.to_numeric(hist["Close"], errors="coerce").dropna()
            return [round(float(v), PRICE_ROUND_DECIMALS) for v in closes.tolist()]
    except Exception as e:
        logger.warning("sparkline_by_timeframe %s %s failed: %s", symbol, timeframe, e)
        return []

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
    """Fetch latest news from Newsdata.io (legacy/fallback function)."""
    if not api_key:
        return []
    try:
        url = (f"https://newsdata.io/api/1/latest?"
               f"apikey={api_key}&q={query}&language={language}"
               f"&size={min(page_size, NEWS_DEFAULT_PAGE_SIZE)}")
        r = safe_get(url)
        data = r.json()
        if data.get("status") == "error":
            err = data.get("results", {})
            msg = err.get("message", "") if isinstance(err, dict) else str(err)
            logger.error("Newsdata.io error: %s", msg)
            return [{"error": msg}]
        return [
            {
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "source": a.get("source_id") or "",
                "url": a.get("link") or "",
                "published": a.get("pubDate", "")
            }
            for a in data.get("results", [])
            if isinstance(a, dict) and a.get("title")
        ]
    except (requests.RequestException, ValueError, KeyError) as e:
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
