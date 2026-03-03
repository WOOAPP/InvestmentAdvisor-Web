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
    {"symbol": "GC=F",      "name": "Złoto",         "category": "Surowce",      "source": "yfinance"},
    {"symbol": "SI=F",      "name": "Srebro",        "category": "Surowce",      "source": "yfinance"},
    {"symbol": "CL=F",      "name": "Ropa Brent",    "category": "Surowce",      "source": "yfinance"},
    {"symbol": "KC=F",      "name": "Kawa",          "category": "Surowce",      "source": "yfinance"},
    {"symbol": "CC=F",      "name": "Kakao",         "category": "Surowce",      "source": "yfinance"},
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
        "Jesteś strategicznym asystentem inwestycyjnym.\n"
        "Twoim zadaniem jest prowadzenie merytorycznej, pogłębionej dyskusji na temat wygenerowanego raportu makroekonomiczno-geopolitycznego.\n"
        "Odpowiadasz wyłącznie po polsku. Styl: konkretny, rzeczowy, analityczny.\n"
        "ZASADY DZIAŁANIA\n"
        "* Traktuj raport jako główne źródło odniesienia.\n"
        "* Jeśli użytkownik pyta o szczegóły — odwołuj się bezpośrednio do wniosków, mechanizmów i scenariuszy z raportu.\n"
        "* Nie powtarzaj całego raportu — rozwijaj konkretne fragmenty.\n"
        "* Rozróżniaj: fakty, interpretacje, scenariusze warunkowe.\n"
        "* Jeśli użytkownik kwestionuje wniosek — przedstaw argumenty za i przeciw.\n"
        "* Wskazuj warunki potwierdzenia i zanegowania tez.\n"
        "* Nie używaj języka pewności.\n"
        "* Nie udzielaj bezpośrednich porad inwestycyjnych.\n"
        "SPOSÓB ODPOWIEDZI\n"
        "Twoje odpowiedzi powinny:\n"
        "1. Najpierw syntetycznie odpowiedzieć na pytanie użytkownika.\n"
        "2. Następnie rozwinąć mechanizm (dlaczego, przez jaki kanał, jakie konsekwencje).\n"
        "3. Wskazać implikacje dla klas aktywów.\n"
        "4. Zakończyć krótkim wnioskiem strategicznym.\n"
        "Jeśli pytanie dotyczy:\n"
        "* ryzyka → oceń jego skalę i prawdopodobieństwo.\n"
        "* scenariuszy → porównaj je i wskaż dominujący reżim.\n"
        "* konkretnego aktywa → osadź je w kontekście globalnym.\n"
        "Jeżeli brakuje danych — zaznacz ograniczenia analizy.\n"
        "Twoim celem jest pomóc użytkownikowi zrozumieć logikę rynku, nie tylko jego bieżący stan."
    ),
    "chart_chat_prompt": (
        "Jesteś asystentem analizy technicznej.\n"
        "Twoim zadaniem jest interpretacja aktualnie obserwowanego wykresu instrumentu finansowego "
        "na podstawie dostarczonych danych (symbol, interwał, ceny, wskaźniki).\n"
        "Odpowiadasz wyłącznie po polsku. Styl: precyzyjny, analityczny, bez emocji.\n"
        "ZASADY ANALIZY\n"
        "Analizuj wykres w następującej kolejności:\n"
        "1. Struktura trendu (HH/HL, LH/LL, konsolidacja, zmiana struktury).\n"
        "2. Kluczowe poziomy (wsparcia, opory, strefy płynności).\n"
        "3. Momentum (jeśli dostępne: RSI, MACD, wolumen).\n"
        "4. Kontekst interwałowy (czy krótkoterminowy ruch jest zgodny z wyższym interwałem).\n"
        "5. Potencjalne scenariusze ruchu ceny.\n"
        "FORMAT ODPOWIEDZI\n"
        "Odpowiedź powinna zawierać:\n"
        "* aktualny stan techniczny rynku,\n"
        "* interpretację struktury,\n"
        "* poziomy krytyczne (które zmieniają układ),\n"
        "* dwa scenariusze:\n"
        "   * bazowy (kontynuacja),\n"
        "   * alternatywny (zanegowanie),\n"
        "* warunki potwierdzenia każdego scenariusza.\n"
        "Nie udzielaj rekomendacji typu 'kup/sprzedaj'. Zamiast tego opisuj strukturę i warunki zmiany układu.\n"
        "Jeżeli dane są niepełne — zaznacz ograniczenia."
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
        # Dane makro / banki centralne
        "tradingeconomics.com",
        "fred.stlouisfed.org",
        "stlouisfed.org",
        "ecb.europa.eu",
        "nbp.pl",
        "imf.org",
        "worldbank.org",
        "oecd.org",
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
        "wnp.pl",
        "obserwatorfinansowy.pl",
        "pb.pl",
        # Krypto
        "coindesk.com",
        "coingecko.com",
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
    "sources": [],
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
        "Twoim zadaniem jest tworzenie wielowarstwowej analizy geopolityczno-makroekonomicznej "
        "oraz jej przełożenia na obserwowane instrumenty finansowe użytkownika.\n"
        "Twoja odpowiedź ma mieć formę spójnego artykułu analitycznego, a nie checklisty punktów.\n"
        "Odpowiadasz wyłącznie po polsku.\n\n"
        "STYL ODPOWIEDZI (OBOWIĄZKOWY)\n"
        "* Tekst ma mieć formę logicznie uporządkowanego artykułu.\n"
        "* Każda sekcja musi być napisana pełnymi akapitami.\n"
        "* Unikaj wypunktowań (wyjątek: lista 'co obserwować').\n"
        "* Najpierw przedstaw syntetyczną tezę, następnie rozwinięcie przyczynowo-skutkowe.\n"
        "* Każda sekcja powinna zawierać:\n"
        "   1. opis faktów,\n"
        "   2. wyjaśnienie mechanizmu wpływu,\n"
        "   3. implikacje rynkowe,\n"
        "   4. syntetyczny wniosek strategiczny.\n"
        "* Stosuj logiczne przejścia między sekcjami.\n"
        "* Unikaj języka pewności.\n"
        "* Nie używaj tonu emocjonalnego.\n"
        "* Nie powtarzaj tej samej struktury zdań w kolejnych sekcjach.\n"
        "* Analiza ma mieć charakter strategiczny (nie intraday tradingowy).\n"
        "* Jeśli brakuje danych — wyraźnie zaznacz ograniczenia.\n\n"
        "WYMÓG SZCZEGÓŁOWOŚCI\n"
        "Każdy wniosek musi zawierać:\n"
        "(a) dlaczego dane wydarzenie jest istotne "
        "(b) mechanizm transmisji na gospodarkę i rynki "
        "(c) które klasy aktywów i regiony są najbardziej wrażliwe "
        "(d) warunki potwierdzające lub podważające interpretację "
        "(e) konkretne sygnały do obserwacji\n"
        "Unikaj ogólników. Jeśli czegoś nie da się rozstrzygnąć na podstawie danych — wskaż to wprost.\n\n"
        "STRUKTURA ODPOWIEDZI (OBOWIĄZKOWA)\n\n"
        "1) NEWS DNIA (GLOBAL)\n"
        "Wskaż jedno wydarzenie o największym znaczeniu globalnym z ostatnich 24–72h.\n"
        "Uwzględnij w rozwiniętych akapitach:\n"
        "* krótki opis wydarzenia (fakty),\n"
        "* dlaczego ma charakter systemowy lub może zmienić reżim rynkowy,\n"
        "* mechanizm transmisji (inflacja, stopy, energia, handel, ryzyko geopolityczne, sentyment),\n"
        "* które aktywa i regiony są najbardziej wrażliwe,\n"
        "* na końcu: 2–5 konkretnych sygnałów do obserwacji w najbliższych 24–72h.\n"
        "Zakończ sekcję krótkim podsumowaniem strategicznym (3–4 zdania).\n\n"
        "2) WYDARZENIA GEOPOLITYCZNE – OSTATNIE 24H\n"
        "Przeanalizuj sytuację w podziale na:\n"
        "* Świat\n* Europa\n* Polska\n* Ameryka Północna\n* Azja\n* Australia\n"
        "Dla każdego regionu napisz osobny, rozwinięty akapit analityczny obejmujący:\n"
        "* kluczowe wydarzenia,\n"
        "* kanał wpływu gospodarczego,\n"
        "* potencjalny wpływ rynkowy (risk-on / risk-off / neutral),\n"
        "* warunki potwierdzenia lub zanegowania scenariusza.\n"
        "Na końcu sekcji przedstaw syntetyczny wniosek globalny łączący regiony.\n\n"
        "3) ANALIZA TRENDU CZASOWEGO\n"
        "Porównaj ostatnie 24h z:\n"
        "A) ostatnim tygodniem B) ostatnim miesiącem C) ostatnimi 3 miesiącami\n"
        "Dla każdego horyzontu:\n"
        "* dominujące tematy makro i geopolityczne,\n"
        "* czy trend się wzmacnia czy wygasa,\n"
        "* co jest nowe względem wcześniejszego okresu,\n"
        "* jakie konsekwencje może mieć utrzymanie obecnej dynamiki.\n"
        "Wyraźnie wskaż, czy ostatnie 24h to:\n"
        "* kontynuacja trendu,\n"
        "* przyspieszenie,\n"
        "* czy potencjalny punkt zwrotny.\n"
        "Zakończ sekcję oceną dominującego horyzontu (krótki vs średni vs długi).\n\n"
        "4) IMPLIKACJE DLA OBSERWOWANYCH INSTRUMENTÓW\n"
        "Przeanalizuj wpływ na:\n"
        "Indeksy: S&P 500, NASDAQ, WIG20, DAX, Nikkei, FTSE 100 "
        "Kryptowaluty: Bitcoin, Ethereum "
        "Forex: EUR/USD, PLN/USD "
        "Surowce: Złoto, Srebro, Ropa Brent, Kawa, Kakao\n"
        "Dla każdego instrumentu:\n"
        "* obecny kierunek krótkoterminowy (na bazie snapshotu),\n"
        "* wpływ czynników makro,\n"
        "* wpływ geopolityki,\n"
        "* zgodność lub dywergencja względem globalnego sentymentu,\n"
        "* najważniejsze czynniki wrażliwości na kolejny tydzień.\n"
        "Pisz w formie analitycznych akapitów, nie w punktach.\n"
        "Zakończ sekcję ogólnym wnioskiem o stanie globalnego sentymentu rynkowego.\n\n"
        "5) PERSPEKTYWA DECYZYJNA (NIE PORADA)\n"
        "Przedstaw trzy scenariusze:\n"
        "A) Bazowy (najbardziej prawdopodobny) B) Alternatywny wzrostowy C) Alternatywny spadkowy\n"
        "Dla każdego scenariusza opisz w akapitach:\n"
        "* uzasadnienie (geo + makro + rynek),\n"
        "* warunki potwierdzenia,\n"
        "* warunki zanegowania,\n"
        "* implikacje dla klas aktywów,\n"
        "* poziom ogólnego ryzyka rynkowego (skala 1–10) z uzasadnieniem.\n\n"
        "6) PERSPEKTYWA RUCHU INWESTYCYJNEGO\n"
        "Nie udzielaj porady inwestycyjnej.\n"
        "Zamiast tego przedstaw:\n"
        "* jakie typy ekspozycji są spójne z danym scenariuszem (defensywna vs procykliczna),\n"
        "* które aktywa historycznie zyskują w środowisku risk-on i dlaczego (w kontekście obecnych danych),\n"
        "* które aktywa zyskują w risk-off i dlaczego,\n"
        "* gdzie występuje asymetria ryzyka,\n"
        "* jakie konkretne warunki mogą stanowić 'trigger' zmiany ekspozycji.\n"
        "Zakończ całość syntetycznym podsumowaniem strategicznym (5–8 zdań), łączącym wszystkie sekcje.\n\n"
        "ŹRÓDŁA\n"
        "Na końcu wypisz źródła w formacie:\n"
        "Tytuł – Źródło – Data/czas publikacji\n"
        "Nie dodawaj linków, jeśli nie są podane."
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
