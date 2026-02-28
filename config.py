import json
import os

CONFIG_FILE = "data/config.json"

DEFAULT_INSTRUMENTS = [
    {"symbol": "SPY",       "name": "S&P 500",      "category": "Akcje",        "source": "yfinance"},
    {"symbol": "QQQ",       "name": "NASDAQ",        "category": "Akcje",        "source": "yfinance"},
    {"symbol": "WIG20.WA",  "name": "WIG20 (GPW)",   "category": "Akcje",        "source": "yfinance"},
    {"symbol": "^GDAXI",    "name": "DAX",           "category": "Akcje",        "source": "yfinance"},
    {"symbol": "^N225",     "name": "Nikkei 225",    "category": "Akcje",        "source": "yfinance"},
    {"symbol": "^FTSE",     "name": "FTSE 100",      "category": "Akcje",        "source": "yfinance"},
    {"symbol": "bitcoin",   "name": "Bitcoin",       "category": "Krypto",       "source": "coingecko"},
    {"symbol": "ethereum",  "name": "Ethereum",      "category": "Krypto",       "source": "coingecko"},
    {"symbol": "EURUSD=X",  "name": "EUR/USD",       "category": "Forex",        "source": "yfinance"},
    {"symbol": "PLNUSD=X",  "name": "PLN/USD",       "category": "Forex",        "source": "yfinance"},
    {"symbol": "GC=F",      "name": "Złoto",         "category": "Surowce",      "source": "yfinance"},
    {"symbol": "SI=F",      "name": "Srebro",        "category": "Surowce",      "source": "yfinance"},
    {"symbol": "CL=F",      "name": "Ropa Brent",    "category": "Surowce",      "source": "yfinance"},
    {"symbol": "KC=F",      "name": "Kawa",          "category": "Surowce",      "source": "yfinance"},
    {"symbol": "CC=F",      "name": "Kakao",         "category": "Surowce",      "source": "yfinance"},
]

DEFAULT_CONFIG = {
    "api_keys": {
        "newsapi": "",
        "openai": "",
        "anthropic": "",
    },
    "ai_provider": "anthropic",
    "ai_model": "claude-opus-4-6",
    "schedule": {
        "enabled": False,
        "times": ["08:00"]
    },
    "instruments": DEFAULT_INSTRUMENTS,
    # legacy – zachowane dla kompatybilności z wykresami
    "instruments_legacy": {
        "stocks": ["SPY", "QQQ", "WIG20.WA", "^GDAXI", "^N225", "^FTSE"],
        "crypto": ["BTC-USD", "ETH-USD"],
        "forex": ["EURUSD=X", "PLNUSD=X"],
        "commodities": ["GC=F", "SI=F", "CL=F", "KC=F", "CC=F"]
    },
    "sources": [],
    "prompt": (
        "Jesteś osobistym doradcą inwestycyjnym. Na podstawie aktualnych danych rynkowych "
        "i wiadomości geopolitycznych oraz gospodarczych przeprowadź kompleksową analizę. "
        "Uwzględnij:\n"
        "1. Aktualną sytuację geopolityczną i jej wpływ na rynki\n"
        "2. Sytuację makroekonomiczną (inflacja, stopy procentowe, PKB)\n"
        "3. Analizę każdej klasy aktywów (akcje, krypto, forex, surowce)\n"
        "4. Poziom ryzyka rynkowego (skala 1-10)\n"
        "5. Konkretne rekomendacje (KUP/SPRZEDAJ/CZEKAJ) dla każdego instrumentu z uzasadnieniem\n"
        "6. Krótko- średnio- i długoterminowe perspektywy\n"
        "Odpowiadaj wyłącznie po polsku. Bądź konkretny i rzeczowy."
    ),
    "language": "pl"
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, val in DEFAULT_CONFIG.items():
            if key not in data:
                data[key] = val
        # Migracja starego formatu instrumentów
        if isinstance(data.get("instruments"), dict):
            data["instruments"] = DEFAULT_INSTRUMENTS
        return data
    return DEFAULT_CONFIG.copy()

def save_config(config):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

config = load_config()