import json
import os

CONFIG_FILE = "data/config.json"

# Mapowanie: klucz w config["api_keys"] -> nazwa zmiennej środowiskowej
ENV_KEY_MAP = {
    "newsapi":    "NEWSAPI_KEY",
    "openai":     "OPENAI_API_KEY",
    "anthropic":  "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

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
        "openrouter": "",
    },
    "ai_provider": "anthropic",
    "ai_model": "claude-opus-4-6",
    "chat_provider": "anthropic",
    "chat_model": "claude-sonnet-4-6",
    "chat_prompt": (
        "Jesteś asystentem inwestycyjnym. Odpowiadaj po polsku, "
        "konkretnie i rzeczowo. Gdy użytkownik pyta o szczegóły, "
        "odwołuj się do danych z raportu."
    ),
    "chart_chat_prompt": (
        "Jesteś asystentem analizy technicznej. Odpowiadaj po polsku, "
        "konkretnie i rzeczowo. Analizuj wykres instrumentu, który "
        "aktualnie ogląda użytkownik. Uwzględniaj trend, wsparcia/opory, "
        "wolumen i średnie kroczące jeśli są dostępne."
    ),
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
    "trusted_domains": [
        "reuters.com",
        "bloomberg.com",
        "cnbc.com",
        "ft.com",
        "wsj.com",
        "bankier.pl",
        "money.pl",
        "investing.com",
        "finance.yahoo.com",
        "tradingview.com",
        "stooq.pl",
        "forsal.pl",
        "parkiet.com",
        "businessinsider.com",
    ],
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


def mask_key(key: str) -> str:
    """Maskuj klucz API — pokaż pierwsze 4 znaki + gwiazdki."""
    if not key or len(key) <= 4:
        return "****" if key else ""
    return key[:4] + "*" * min(len(key) - 4, 12)


def _apply_env_overrides(data: dict) -> dict:
    """Zmienne środowiskowe mają priorytet nad wartościami z pliku."""
    api_keys = data.setdefault("api_keys", {})
    for config_key, env_name in ENV_KEY_MAP.items():
        env_val = os.environ.get(env_name, "").strip()
        if env_val:
            api_keys[config_key] = env_val
    return data


def get_api_key(config: dict, key_name: str) -> str:
    """Pobierz klucz API z env (priorytet) lub config. Zwraca '' gdy brak."""
    env_name = ENV_KEY_MAP.get(key_name, "")
    if env_name:
        env_val = os.environ.get(env_name, "").strip()
        if env_val:
            return env_val
    return config.get("api_keys", {}).get(key_name, "")


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
    else:
        data = DEFAULT_CONFIG.copy()
    return _apply_env_overrides(data)


def save_config(config):
    """Zapisz config. Klucze z env nie są zapisywane do pliku."""
    os.makedirs("data", exist_ok=True)
    to_save = json.loads(json.dumps(config))  # deep copy
    # Nie zapisuj kluczy pochodzących z env — zostaw puste
    saved_keys = to_save.get("api_keys", {})
    for config_key, env_name in ENV_KEY_MAP.items():
        if os.environ.get(env_name, "").strip():
            saved_keys[config_key] = ""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)


config = load_config()
