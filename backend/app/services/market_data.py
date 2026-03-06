"""Pobieranie danych rynkowych — wersja web, niezależna od aplikacji desktopowej.

Kopia z modules/market_data.py z dostosowanymi importami.
Źródła danych: yfinance, CoinGecko, Stooq.
"""

import re
import yfinance as yf
import requests
from datetime import datetime
from backend.app.services.constants import APP_TIMEZONE
import logging
import threading as _threading
import time as _time
import pandas as pd

from .http_client import safe_get
from .constants import (
    FX_CACHE_TTL, YFINANCE_HISTORY_PERIOD,
    PRICE_ROUND_DECIMALS, CHANGE_PCT_ROUND_DECIMALS,
    NEWS_DEFAULT_PAGE_SIZE,
)

# Dozwolony wzorzec dla symboli finansowych (używany w URL).
# Obejmuje yfinance (^GDAXI, EURUSD=X, GC=F, WIG20.WA),
# CoinGecko slug (bitcoin, ethereum) i Stooq (wig20).
_SYMBOL_RE = re.compile(r'^[\w\-\.\^=]+$', re.ASCII)


def _validate_symbol(symbol: str, source: str = "") -> bool:
    """Zwraca True jeśli symbol jest bezpieczny do wstawienia w URL."""
    if not symbol or len(symbol) > 50:
        return False
    return bool(_SYMBOL_RE.match(symbol))


# ── COINGECKO CACHE ──
_CG_PRICE_TTL     = 600   # 10 min
_CG_SPARKLINE_TTL = 3600  # 1 h
_cg_price_cache    = {}   # {coin_id: (data_dict, ts)}
_cg_sparkline_cache = {}  # {coin_id: (list, ts)}
_cg_lock           = _threading.Lock()

# ── COINGECKO RATE LIMITER ──
_CG_MIN_INTERVAL = 2.5  # sekundy między requestami (free tier ~30 req/min)
_cg_last_req_ts  = 0.0
_cg_req_lock     = _threading.Lock()

# ── COINGECKO 429 BACKOFF ──
_CG_BACKOFF_SECONDS = 60
_cg_backoff_until   = 0.0


def _cg_rate_wait():
    global _cg_last_req_ts
    with _cg_req_lock:
        now = _time.time()
        wait = _CG_MIN_INTERVAL - (now - _cg_last_req_ts)
        if wait > 0:
            _time.sleep(wait)
        _cg_last_req_ts = _time.time()


logger = logging.getLogger(__name__)


# ── YAHOO FINANCE ──────────────────────────────────────────────────
def get_yfinance_data(symbol, name=""):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=YFINANCE_HISTORY_PERIOD)
        if hist.empty:
            return {"name": name or symbol, "error": "brak danych"}

        closes = pd.to_numeric(hist["Close"], errors="coerce").dropna()
        if closes.empty:
            return {"name": name or symbol, "error": "brak danych cenowych"}

        # Użyj fast_info dla aktualnej ceny (real-time) zamiast wczorajszego close
        current = None
        prev = None
        try:
            fast = ticker.fast_info
            lp = fast.last_price
            pc = fast.previous_close
            if lp is not None and not pd.isna(lp):
                current = float(lp)
            if pc is not None and not pd.isna(pc):
                prev = float(pc)
        except Exception:
            pass

        if current is None:
            current = float(closes.iloc[-1])
        if prev is None:
            prev = float(closes.iloc[-2]) if len(closes) >= 2 else current

        change = current - prev
        change_pct = (change / prev) * 100 if prev != 0 else 0

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
            "timestamp": datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M"),
        }
    except (requests.RequestException, KeyError, ValueError, TypeError) as e:
        logger.warning("yfinance %s failed: %s", symbol, e)
        return {"name": name or symbol, "error": str(e)}


# ── COINGECKO ──────────────────────────────────────────────────────
def _cg_is_backed_off():
    return _time.time() < _cg_backoff_until


def _cg_fetch_prices_batch(coin_ids):
    global _cg_backoff_until
    if _cg_is_backed_off():
        logger.debug("CoinGecko backoff active, skipping request")
        return {}
    _cg_rate_wait()
    ids_str = ",".join(coin_ids)
    url = (
        f"https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids_str}&vs_currencies=usd"
        f"&include_24hr_change=true&include_24hr_vol=true"
    )
    try:
        r = safe_get(url)
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 429:
            _cg_backoff_until = _time.time() + _CG_BACKOFF_SECONDS
            logger.warning("CoinGecko 429 — backoff %ds", _CG_BACKOFF_SECONDS)
            return {}
        raise
    batch = r.json()
    ts = _time.time()
    with _cg_lock:
        for cid, data in batch.items():
            _cg_price_cache[cid] = (data, ts)
    return batch


def _cg_get_sparkline(coin_id):
    with _cg_lock:
        cached = _cg_sparkline_cache.get(coin_id)
    if cached and (_time.time() - cached[1]) < _CG_SPARKLINE_TTL:
        return cached[0]
    if _cg_is_backed_off():
        return cached[0] if cached else []
    try:
        _cg_rate_wait()
        chart_url = (
            f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            f"/market_chart?vs_currency=usd&days=5&interval=daily"
        )
        cr = safe_get(chart_url)
        sparkline = [round(p[1], PRICE_ROUND_DECIMALS) for p in cr.json().get("prices", [])]
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.debug("CoinGecko sparkline for %s unavailable: %s", coin_id, e)
        return cached[0] if cached else []
    with _cg_lock:
        _cg_sparkline_cache[coin_id] = (sparkline, _time.time())
    return sparkline


def _cg_build_result(coin_id, name, data, sparkline):
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
        "timestamp": datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M"),
    }


def get_coingecko_data(coin_id, name=""):
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
            if cached:
                data = cached[0]
            else:
                return {"name": name or coin_id, "error": str(e)}
        if not data and cached:
            data = cached[0]
    if not data:
        return {"name": name or coin_id, "error": "brak danych CoinGecko"}
    sparkline = _cg_get_sparkline(coin_id)
    return _cg_build_result(coin_id, name, data, sparkline)


# ── STOOQ ──────────────────────────────────────────────────────────
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
            "high_5d": round(float(parts[4]), PRICE_ROUND_DECIMALS),
            "low_5d": round(float(parts[5]), PRICE_ROUND_DECIMALS),
            "sparkline": [round(open_, PRICE_ROUND_DECIMALS), round(close, PRICE_ROUND_DECIMALS)],
            "source": "stooq",
            "timestamp": datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M"),
        }
    except (requests.RequestException, ValueError, IndexError) as e:
        logger.warning("Stooq %s failed: %s", symbol, e)
        return {"name": name or symbol, "error": str(e)}


# ── FX RATES CACHE ─────────────────────────────────────────────────
_fx_cache = {}
_fx_lock  = _threading.Lock()
_FX_CACHE_TTL = FX_CACHE_TTL


def get_fx_to_usd(currency):
    """Zwraca kurs currency → USD. USD = 1.0. None przy błędzie."""
    currency = currency.upper()
    if currency == "USD":
        return 1.0
    cache_key = f"{currency}USD"
    with _fx_lock:
        cached = _fx_cache.get(cache_key)
        if cached and (_time.time() - cached[1]) < _FX_CACHE_TTL:
            return cached[0]
    try:
        ticker = yf.Ticker(f"{currency}USD=X")
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
        logger.warning("FX fetch %sUSD=X failed: %s", currency, e)
        return None


# ── WSZYSTKIE INSTRUMENTY ──────────────────────────────────────────
def get_all_instruments(instruments_config):
    """
    instruments_config: [{"symbol": "BTC-USD", "name": "Bitcoin",
                           "category": "crypto", "source": "coingecko"}, ...]

    CoinGecko: pobierane jednym zbiorczym żądaniem (batch).
    yfinance/stooq: osobny request per instrument.
    """
    results = {}
    cg_pending = []

    for inst in instruments_config:
        symbol = inst.get("symbol", "")
        name   = inst.get("name", symbol)
        source = inst.get("source", "yfinance")
        if not symbol:
            continue
        if not _validate_symbol(symbol, source):
            logger.warning("Skipping invalid symbol: %r", symbol)
            results[symbol] = {"name": name, "error": "invalid symbol"}
            continue
        if source == "coingecko":
            cg_pending.append((symbol, symbol.lower(), name))
        elif source == "stooq":
            results[symbol] = get_stooq_data(symbol, name)
        else:
            results[symbol] = get_yfinance_data(symbol, name)

    if cg_pending:
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
        for symbol, coin_id, name in cg_pending:
            with _cg_lock:
                cached = _cg_price_cache.get(coin_id)
            if cached:
                sparkline = _cg_get_sparkline(coin_id)
                results[symbol] = _cg_build_result(coin_id, name, cached[0], sparkline)
            else:
                results[symbol] = {"name": name, "error": "CoinGecko niedostępne (rate limit)"}

    return results


# ── SPARKLINE PO PRZEDZIALE CZASOWYM ──────────────────────────────
_SPARK_CFG: dict[str, dict] = {
    # Granularność świec (web frontend)
    "5m":  {"yf_period": "1d",  "yf_interval": "5m",  "cg_days": "1"},
    "15m": {"yf_period": "5d",  "yf_interval": "15m", "cg_days": "1"},
    "1h":  {"yf_period": "5d",  "yf_interval": "1h",  "cg_days": "1"},
    "24h": {"yf_period": "60d", "yf_interval": "1d",  "cg_days": "30"},
    "72h": {"yf_period": "1y",  "yf_interval": "1d",  "cg_days": "90"},
    # Zachowane dla kompatybilności
    "1m":  {"yf_period": "1d",  "yf_interval": "1m",  "cg_days": "1"},
}


def get_sparkline_by_timeframe(symbol, timeframe, source="yfinance"):
    """Zwraca listę cen dla danego interwału czasowego."""
    cfg = _SPARK_CFG.get(timeframe, _SPARK_CFG["1h"])
    try:
        if source == "coingecko":
            coin_id = symbol.lower()
            if _cg_is_backed_off():
                logger.debug("CoinGecko backoff, skipping sparkline for %s", coin_id)
                return []
            _cg_rate_wait()
            url = (
                f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                f"/market_chart?vs_currency=usd&days={cfg['cg_days']}"
            )
            r = safe_get(url)
            return [round(float(p[1]), PRICE_ROUND_DECIMALS) for p in r.json().get("prices", [])]
        elif source == "stooq":
            return []  # stooq nie wspiera danych intraday
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
        "📊 Inne": [],
    }

    for symbol, d in all_data.items():
        if "error" in d:
            line = f"{d.get('name', symbol)}: błąd - {d['error']}"
        else:
            arrow = "▲" if d.get("change_pct", 0) >= 0 else "▼"
            line = (
                f"{d.get('name', symbol)}: {d.get('price', 0)} "
                f"{arrow} {d.get('change_pct', 0):+.2f}%"
            )
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
