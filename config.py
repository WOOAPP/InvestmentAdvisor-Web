import json
import os

CONFIG_FILE = "data/config.json"

# Mapowanie: klucz w config["api_keys"] -> nazwa zmiennej środowiskowej
ENV_KEY_MAP = {
    "newsdata":   "NEWSDATA_KEY",
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
    {"symbol": "^DJI",      "name": "Dow Jones",     "category": "Akcje",        "source": "yfinance"},
    {"symbol": "^HSI",      "name": "Hang Seng",     "category": "Akcje",        "source": "yfinance"},
    {"symbol": "GC=F",      "name": "Złoto",         "category": "Surowce",      "source": "yfinance"},
    {"symbol": "SI=F",      "name": "Srebro",        "category": "Surowce",      "source": "yfinance"},
    {"symbol": "CL=F",      "name": "Ropa Brent",    "category": "Surowce",      "source": "yfinance"},
    {"symbol": "NG=F",      "name": "Gaz ziemny",    "category": "Surowce",      "source": "yfinance"},
    {"symbol": "HG=F",      "name": "Miedź",         "category": "Surowce",      "source": "yfinance"},
    {"symbol": "PA=F",      "name": "Pallad",        "category": "Surowce",      "source": "yfinance"},
    {"symbol": "PL=F",      "name": "Platyna",       "category": "Surowce",      "source": "yfinance"},
    {"symbol": "ZW=F",      "name": "Pszenica",      "category": "Surowce",      "source": "yfinance"},
    {"symbol": "ZS=F",      "name": "Soja",          "category": "Surowce",      "source": "yfinance"},
    {"symbol": "ZC=F",      "name": "Kukurydza",     "category": "Surowce",      "source": "yfinance"},
    {"symbol": "KC=F",      "name": "Kawa",          "category": "Surowce",      "source": "yfinance"},
    {"symbol": "CC=F",      "name": "Kakao",         "category": "Surowce",      "source": "yfinance"},
    {"symbol": "DX-Y.NYB",  "name": "US Dollar Index","category": "Forex",        "source": "yfinance"},
]

DEFAULT_CONFIG = {
    "api_keys": {
        "newsdata": "",
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
        "stocks": ["SPY", "QQQ", "WIG20.WA", "^GDAXI", "^N225", "^FTSE", "^DJI", "^HSI"],
        "crypto": ["BTC-USD", "ETH-USD"],
        "forex": ["EURUSD=X", "PLNUSD=X", "DX-Y.NYB"],
        "commodities": ["GC=F", "SI=F", "CL=F", "NG=F", "HG=F", "PA=F", "PL=F",
                        "ZW=F", "ZS=F", "ZC=F", "KC=F", "CC=F"]
    },
    "trusted_domains": [
        # Agencje / media globalne
        "reuters.com",
        "bloomberg.com",
        "cnbc.com",
        "ft.com",
        "wsj.com",
        "bbc.com",
        "bbc.co.uk",
        "theguardian.com",
        "nytimes.com",
        "economist.com",
        "aljazeera.com",
        "apnews.com",
        # Finanse / rynki
        "investing.com",
        "finance.yahoo.com",
        "tradingview.com",
        "marketwatch.com",
        "seekingalpha.com",
        "businessinsider.com",
        "zerohedge.com",
        "barchart.com",
        "worldgovernmentbonds.com",
        # Dane makro / banki centralne
        "tradingeconomics.com",
        "fred.stlouisfed.org",
        "stlouisfed.org",
        "federalreserve.gov",
        "ecb.europa.eu",
        "nbp.pl",
        "imf.org",
        "worldbank.org",
        "oecd.org",
        # Geopolityka / think-tanki
        "foreignaffairs.com",
        "foreignpolicy.com",
        "csis.org",
        "cfr.org",
        "chathamhouse.org",
        "atlanticcouncil.org",
        "iswresearch.org",
        "iiss.org",
        "stratfor.com",
        "al-monitor.com",
        # Polska
        "bankier.pl",
        "money.pl",
        "stooq.pl",
        "stooq.com",
        "forsal.pl",
        "parkiet.com",
        "gpw.pl",
        "analizy.pl",
        "pap.pl",
        "biznes.pap.pl",
        "wnp.pl",
        "obserwatorfinansowy.pl",
        "pb.pl",
        "stat.gov.pl",
        "osw.waw.pl",
        "pism.pl",
        "defence24.pl",
        "energetyka24.com",
        "euractiv.pl",
        "politykainsight.pl",
        "klubjagiellonski.pl",
        "strategyandfuture.org",
        "eastbook.eu",
        "tvpworld.com",
        "tvn24.pl",
        "polsatnews.pl",
        # Krypto
        "coindesk.com",
        "coingecko.com",
        "coinmarketcap.com",
        "cointelegraph.com",
        "decrypt.co",
        "theblock.co",
        # Surowce / energia
        "kitco.com",
        "oilprice.com",
        "ino.com",
        # API news
        "newsdata.io",
    ],
    "sources": [
        # Wiadomości finansowe
        "https://www.bloomberg.com",
        "https://www.reuters.com",
        "https://www.ft.com",
        "https://www.wsj.com",
        "https://www.cnbc.com",
        "https://www.marketwatch.com",
        "https://www.investing.com",
        "https://www.tradingview.com",
        "https://www.zerohedge.com",
        "https://www.federalreserve.gov",
        # Geopolityka / think-tanki
        "https://www.foreignaffairs.com",
        "https://foreignpolicy.com",
        "https://www.csis.org",
        "https://www.cfr.org",
        "https://www.chathamhouse.org",
        "https://www.atlanticcouncil.org",
        "https://www.iswresearch.org",
        "https://www.iiss.org",
        "https://www.stratfor.com",
        "https://www.al-monitor.com",
        # Dane rynkowe
        "https://www.coingecko.com",
        "https://coinmarketcap.com",
        "https://stooq.pl",
        "https://finance.yahoo.com",
        "https://www.marketwatch.com/tools/marketsummary",
        "https://www.barchart.com",
        "https://www.worldgovernmentbonds.com",
        "https://fred.stlouisfed.org",
        # Polska
        "https://www.bankier.pl",
        "https://www.pb.pl",
        "https://www.parkiet.com",
        "https://www.money.pl",
        "https://biznes.pap.pl",
        "https://www.gpw.pl",
        "https://www.nbp.pl",
        "https://stat.gov.pl",
        "https://www.obserwatorfinansowy.pl",
        "https://www.osw.waw.pl",
        "https://www.pism.pl",
        "https://www.defence24.pl",
        "https://www.energetyka24.com",
        "https://www.euractiv.pl",
        "https://www.politykainsight.pl",
        "https://www.klubjagiellonski.pl",
        "https://strategyandfuture.org",
        "https://www.eastbook.eu",
        "https://tvpworld.com",
        "https://tvn24.pl",
        "https://www.polsatnews.pl",
    ],
    "profile_prompt": (
        "Opisz ten instrument w trzech sekcjach:\n\n"
        "## 1. Czym jest\n"
        "Krótki opis instrumentu w kontekście jego kategorii.\n\n"
        "## 2. Co wpływa na kurs\n"
        "Najważniejsze czynniki wpływające na wahania ceny "
        "(makro, geopolityka, sezonowość, korelacje).\n\n"
        "## 3. Na co wpływa\n"
        "Gdzie jest \"transmisja\" na inne rynki, branże, instrumenty.\n\n"
        "Bądź zwięzły (max 300 słów łącznie). Używaj konkretnych przykładów."
    ),
    "prompt": (
        "Jesteś analitykiem makroekonomicznym. Na podstawie danych rynkowych, "
        "newsów z wielu okien czasowych oraz analizy trendów, przeprowadź analizę "
        "w następującej strukturze:\n"
        "0) NEWS DNIA — omów najważniejszy news i jego implikacje rynkowe\n"
        "1) GEO 24H — sytuacja per region (Świat/Europa/Polska/Am.Płn./Azja/Australia)\n"
        "2) PORÓWNANIE TRENDU: 24h vs 7d vs 30d vs 90d — kontynuacje, anomalie, punkty zwrotne\n"
        "3) IMPLIKACJE DLA INSTRUMENTÓW — jak powyższe wpływa na aktywa ze snapshotu\n"
        "4) SCENARIUSZE + RYZYKO (skala 1–10) — scenariusz bazowy, optymistyczny, pesymistyczny\n"
        "5) PERSPEKTYWA RUCHU — kierunki i prawdopodobieństwo, ale NIE porada inwestycyjna\n"
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
