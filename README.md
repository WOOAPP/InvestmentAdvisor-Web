# Investment Advisor

Desktopowa aplikacja do analizy rynków finansowych z AI. Pobiera dane rynkowe w czasie rzeczywistym, wiadomości makroekonomiczne (Newsdata.io), treści ze stron WWW (scraper), a następnie generuje szczegółowe raporty inwestycyjne za pomocą modeli AI (Anthropic Claude / OpenAI GPT / OpenRouter). Interfejs w Tkinter z motywem Catppuccin Mocha.

---

## Spis treści

- [Pobieranie](#pobieranie)
- [Funkcje](#funkcje)
- [Źródła danych rynkowych](#źródła-danych-rynkowych)
- [Architektura](#architektura)
- [Wymagania (uruchomienie ze źródeł)](#wymagania-uruchomienie-ze-źródeł)
- [Konfiguracja kluczy API](#konfiguracja-kluczy-api)
- [Uruchomienie](#uruchomienie)
- [Konfiguracja](#konfiguracja)
- [Dostępne modele AI](#dostępne-modele-ai)
- [Baza danych](#baza-danych)
- [Bezpieczeństwo](#bezpieczeństwo)
- [Testy](#testy)
- [Struktura projektu](#struktura-projektu)
- [Budowanie plików wykonywalnych](#budowanie-plików-wykonywalnych)
- [Licencja](#licencja)

---

## Pobieranie

Gotowe pliki wykonywalne — **nie wymagają Pythona ani instalacji**:

| System | Plik |
|--------|------|
| **Windows** | [InvestmentAdvisor-windows-x86_64.exe](https://github.com/WOOAPP/InvestmentAdvisor/releases/latest) |
| **Linux** | [InvestmentAdvisor-linux-x86_64](https://github.com/WOOAPP/InvestmentAdvisor/releases/latest) |

> Na Windows może pojawić się ostrzeżenie SmartScreen — kliknij **"More info"** → **"Run anyway"**.

---

## Funkcje

### Dashboard
- Kafelki z cenami instrumentów w czasie rzeczywistym (auto-odświeżanie co sekundę)
- Mini wykresy (sparklines) z wyborem zakresu: 1m / 15m / 1h / 6h / 24h
- Miernik ryzyka rynkowego (gauge) wyliczany z ostatniego raportu AI
- Podgląd ostatniego raportu z renderowaniem Markdown
- Pasek informacyjny: model AI, tokeny, koszt analizy (USD + PLN)

### Analiza AI
- Generowanie raportów przez: **Anthropic** (Claude Opus / Sonnet / Haiku), **OpenAI** (GPT-4.1, o3, o4-mini), **OpenRouter** (dowolny model)
- Struktura raportu: 5 najważniejszych wydarzeń globalnych → Sytuacja per region → Porównanie trendów → Implikacje → Scenariusze + ryzyko
- Dane wejściowe: ceny instrumentów + wiadomości (Newsdata.io) + treść ze stron WWW (scraper) + trend makro (7d/30d/90d)
- Automatyczna analiza wg harmonogramu (np. 08:00, 16:00)
- Eksport raportu do PDF

### Wykresy
- Interaktywne wykresy cenowe: 1D / 5D / 1M / 3M / 6M / YTD / 1Y / 5Y / MAX
- Średnie kroczące MA20 i MA50 (opcjonalne)
- Wykres wolumenu
- Porównanie dwóch instrumentów na jednym wykresie
- Wbudowany chat AI do analizy technicznej (z kontekstem wykresu)

### Kalendarz ekonomiczny
- Dane z ForexFactory (JSON API, cache 1h)
- Zakres: od dziś do końca bieżącego tygodnia
- Filtr wg wpływu: Wysoki 🔴 / Średni 🟡 / Niski ⚪
- Kolorowanie: dziś (bold + tło), przeszłe (przyciemnione), przyszłe (normalne)
- Opis znaczenia 100+ typów wydarzeń makro (po polsku)
- Dwuklik → AI analiza wybranego wydarzenia

### Portfel
- **3 zakładki**: Obserwowane (watchlist), Gra na wzrosty (long), Gra na spadki (short)
- Ceny aktualne pobierane na żywo, przeliczanie P&L w USD i walucie lokalnej
- Obsługa walut: USD, PLN, EUR z automatycznym kursem FX
- Przycisk "Aktualna" — wypełnia bieżącą cenę rynkową

### Chat AI
- Rozmowa z modelem AI z pełnym kontekstem:
  - Aktualne ceny instrumentów
  - Ostatni raport analizy
  - **Pełna zawartość portfela** (wszystkie 3 zakładki z pozycjami i P&L)
- Osobny wybór modelu/providera dla czatu
- Renderowanie Markdown w odpowiedziach
- Animacja oczekiwania (typing indicator) podczas generowania odpowiedzi
- Otwieranie w osobnym oknie (popup)

### Trend makro
- Pipeline: Newsdata.io → klasyfikacja regionalna/tematyczna → scoring → top news dnia
- Porównanie trendów: 24h vs 7d vs 30d vs 90d
- Automatyczne wykrywanie zmian sentymentu, anomalii i punktów zwrotnych

---

## Źródła danych rynkowych

| Źródło | Instrumenty | Uwagi |
|--------|-------------|-------|
| **yfinance** | Akcje, indeksy, forex, surowce | Domyślne źródło |
| **CoinGecko** | Kryptowaluty | Rate limit 2.5s, cache 10 min |
| **Stooq** | Instrumenty polskie (WIG, mWIG40) | CSV API |

**Domyślne instrumenty** (konfigurowalne w UI):
SPY, QQQ, WIG20, DAX, Nikkei 225, FTSE 100, Bitcoin, Ethereum, DXY, EUR/USD, USD/PLN, EUR/PLN, Złoto, Srebro, Ropa, Kawa, Kakao, Dow Jones, Hang Seng, Gaz ziemny, Miedź, Pallad, Platyna, Pszenica, Soja, Kukurydza.

---

## Architektura

```
User → GUI (main.py / Tkinter)
        │
        ├── market_data.py ──→ yfinance / CoinGecko / Stooq
        │       └── http_client.py (retry + backoff)
        │
        ├── macro_trend.py ──→ news_store.py ──→ Newsdata.io API
        │       ├── news_classifier.py (region/temat)
        │       ├── news_of_day.py (scoring → top news)
        │       └── trend_narrative.py (7d/30d/90d porównania)
        │
        ├── scraper.py ──→ url_validator.py (SSRF) ──→ HTTP
        │
        ├── calendar_data.py ──→ ForexFactory JSON
        │
        └── ai_engine.py ──→ Anthropic / OpenAI / OpenRouter
                │
                └── Raport → database.py → SQLite
```

- Ciężkie I/O w wątkach daemon
- Aktualizacje UI przez `self.after(0, callback)` (thread-safe)
- Cache: CoinGecko 10 min, FX rates konfigurowalne, kalendarz 1h

---

## Wymagania (uruchomienie ze źródeł)

- Python 3.10+
- System z Tkinter (wbudowane w większość dystrybucji Pythona)

```bash
pip install anthropic openai yfinance requests beautifulsoup4 matplotlib pandas schedule fpdf2
```

---

## Konfiguracja kluczy API

Klucze API ustawia się jako **zmienne środowiskowe** (zalecane) lub w UI (Ustawienia → Klucze API).

Zmienne środowiskowe mają priorytet nad `data/config.json` — klucze z ENV nie są zapisywane do pliku.

| Zmienna | Opis | Wymagane? |
|---------|------|-----------|
| `ANTHROPIC_API_KEY` | Klucz Anthropic (Claude) | Wymagane dla Anthropic |
| `OPENAI_API_KEY` | Klucz OpenAI | Wymagane dla OpenAI |
| `OPENROUTER_API_KEY` | Klucz OpenRouter | Wymagane dla OpenRouter |
| `NEWSDATA_KEY` | Klucz Newsdata.io (wiadomości) | Opcjonalne (wzbogaca raporty) |

### Przykład (Linux/macOS)

```bash
export ANTHROPIC_API_KEY="sk-ant-xxxx..."
export NEWSDATA_KEY="pub_xxxx..."
python main.py
```

### Przykład (Windows PowerShell)

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-xxxx..."
$env:NEWSDATA_KEY = "pub_xxxx..."
python main.py
```

Lub utwórz plik `.env` i załaduj go przed uruchomieniem.

---

## Uruchomienie

```bash
python main.py
```

Auto-analiza (tryb cron):
```bash
python main.py --auto-analysis
```

Przy pierwszym uruchomieniu aplikacja tworzy:
- `data/config.json` — konfiguracja użytkownika
- `data/advisor.db` — baza danych SQLite

---

## Konfiguracja

Plik `data/config.json` tworzony automatycznie. Kluczowe pola:

| Pole | Opis |
|------|------|
| `api_keys.anthropic` | Klucz API Anthropic |
| `api_keys.openai` | Klucz API OpenAI |
| `api_keys.openrouter` | Klucz API OpenRouter |
| `api_keys.newsdata` | Klucz API Newsdata.io |
| `ai_provider` | `"anthropic"`, `"openai"` lub `"openrouter"` |
| `ai_model` | np. `"claude-opus-4-6"`, `"gpt-4.1"`, `"openai/gpt-4o"` |
| `chat_provider` / `chat_model` | Osobny provider/model dla czatu |
| `instruments` | Lista instrumentów: `[{symbol, name, category, source}]` |
| `sources` | URL-e do web scrapingu |
| `trusted_domains` | Allowlist domen dla scrapera (80+ domyślnych) |
| `prompt` | Prompt systemowy do analizy |
| `chat_prompt` | Prompt systemowy do czatu |
| `schedule.enabled` | Automatyczna analiza (bool) |
| `schedule.times` | Godziny analiz np. `["08:00", "16:00"]` |

---

## Dostępne modele AI

### Anthropic
`claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`

### OpenAI
`gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `o3`, `o3-mini`, `o4-mini`, `o1`, `o1-preview`, `o1-mini`

### OpenRouter
Dowolny model dostępny na OpenRouter w formacie `provider/model` (np. `openai/gpt-4o`).

Można też wpisać własny model w polu "Custom model" w Ustawieniach.

---

## Baza danych

Plik: `data/advisor.db` (SQLite, nie wersjonowany). Automatyczne migracje przy starcie.

| Tabela | Zawartość |
|--------|----------|
| `reports` | Raporty AI (provider, model, analiza, poziom ryzyka, tokeny) |
| `market_snapshots` | Historia cen instrumentów |
| `alerts` | Alerty cenowe (widziane/nie widziane) |
| `portfolio` | Pozycje portfela (symbol, ilość, cena zakupu, waluta, kurs FX) |
| `instrument_profiles` | Cache profili instrumentów generowanych przez AI |
| `news_items` | Artykuły newsowe z deduplikacją hash (5 indeksów) |

Dostęp thread-safe przez `threading.RLock`.

---

## Bezpieczeństwo

### Ochrona SSRF (`modules/url_validator.py`)
Walidacja każdego URL przed żądaniem scrapera:
1. Kontrola schematu — tylko `http` / `https`
2. Blokada literalnych IP — prywatne, loopback, zarezerwowane, link-local, multicast
3. Blokada znanych hostów — `localhost`, `ip6-localhost` itd.
4. Kontrola DNS — rozwiązuje hostname, blokuje jeśli IP prywatne/loopback
5. Allowlist domen — jeśli `trusted_domains` skonfigurowane, tylko dozwolone domeny

### Klient HTTP (`modules/http_client.py`)
- Retry z exponential backoff na 429/500/502/503/504
- Timeout: connect 8s, read 15s
- Maskowanie URL w logach — parametry `apiKey`, `api_key`, `token`, `secret`, `password`
- Singleton session (thread-safe)

### Scraper (`modules/scraper.py`)
- Walidacja URL przez `url_validator` przed każdym żądaniem
- Limit rozmiaru odpowiedzi: 2 MB
- Max 3 przekierowania, max 20 URL na sesję
- Parallel scraping: ThreadPoolExecutor (max 6 workerów)

### Klucze API
- Zmienne środowiskowe mają priorytet nad plikiem konfiguracji
- Klucze z ENV nie są zapisywane do `config.json`
- `mask_key()` maskuje klucze w UI
- Sekcja ustawień chroniona hasłem

---

## Testy

```bash
python -m unittest discover tests/ -v
```

13 plików testowych, 242+ test cases:

| Plik | Zakres |
|------|--------|
| `test_ai_engine.py` | Dispatch providerów, zliczanie tokenów, budowanie promptów |
| `test_charts.py` | Szerokość słupków, kolory wolumenu, formatowanie osi X |
| `test_database.py` | Pełny CRUD, migracje, izolacja przez temp DB |
| `test_http_client.py` | Maskowanie URL w logach |
| `test_macro_trend.py` | Slimming payloadu, formatowanie LLM |
| `test_market_data.py` | yfinance/CoinGecko/Stooq, cache FX, formatowanie |
| `test_news_classifier.py` | Klasyfikacja region/temat, priorytet |
| `test_news_of_day.py` | Komponenty scoringu, selekcja, uzasadnienie |
| `test_news_store.py` | Deduplikacja, okna czasowe, fail-fast na auth error |
| `test_trend_narrative.py` | Agregacja, porównanie okien, sygnały |
| `test_ui_helpers.py` | Renderowanie Markdown, cykl życia spinnera |
| `test_url_validator.py` | Ochrona SSRF, blokowanie IP, allowlist (28 testów) |

---

## Struktura projektu

```
InvestmentAdvisor/
├── main.py                    # Aplikacja Tkinter — GUI (~4300 LOC)
├── config.py                  # Konfiguracja, env overrides, domyślne instrumenty
├── constants.py               # 73 parametry tuningowe (timeouty, limity, wagi)
├── InvestmentAdvisor.spec     # Konfiguracja PyInstaller
├── modules/
│   ├── ai_engine.py           # Dispatch: Anthropic / OpenAI / OpenRouter
│   ├── market_data.py         # Dane rynkowe: yfinance, CoinGecko, Stooq
│   ├── database.py            # SQLite CRUD — raporty, snapshoty, alerty, portfel
│   ├── charts.py              # Wykresy Matplotlib w Tkinter (cena, wolumen, gauge)
│   ├── scraper.py             # Równoległy scraper z walidacją URL (BeautifulSoup)
│   ├── http_client.py         # Współdzielona sesja HTTP z retry i backoff
│   ├── url_validator.py       # Ochrona SSRF: schemat/IP/DNS + allowlist domen
│   ├── calendar_data.py       # Kalendarz ekonomiczny (ForexFactory JSON)
│   ├── news_store.py          # Pobieranie newsów (Newsdata.io), deduplikacja, SQLite
│   ├── news_classifier.py     # Klasyfikacja region/temat (regex, bez ML)
│   ├── news_of_day.py         # Scoring newsów — wybór najważniejszych
│   ├── macro_trend.py         # Orkiestrator: news → klasyfikacja → trend → LLM
│   ├── trend_narrative.py     # Agregacja trendów, porównanie okien (24h/7d/30d/90d)
│   ├── openai_pricing.py      # Kalkulator kosztów LLM (cache 3-poziomowy)
│   ├── ui_helpers.py          # Markdown renderer, BusySpinner, ChatTypingIndicator
│   └── exceptions.py          # Wyjątki: DataFetchError, AIProviderError, ScraperError
├── tests/                     # 13 plików testowych, 242+ test cases
├── .github/
│   └── workflows/
│       └── build-and-release.yml  # CI: budowanie EXE (Windows + Linux)
└── data/
    ├── config.json            # Konfiguracja użytkownika (nie wersjonowane)
    └── advisor.db             # Baza SQLite (nie wersjonowane)
```

---

## Budowanie plików wykonywalnych

### Lokalne budowanie (PyInstaller)

```bash
pip install pyinstaller
pyinstaller InvestmentAdvisor.spec
```

Wynikowy plik w `dist/InvestmentAdvisor` (Linux) lub `dist/InvestmentAdvisor.exe` (Windows).

### CI/CD (GitHub Actions)

Workflow `.github/workflows/build-and-release.yml` buduje pliki EXE automatycznie:
1. Utwórz tag: `git tag v1.x.0 && git push --tags`
2. Uruchom workflow ręcznie w GitHub Actions (`workflow_dispatch`)
3. Pliki EXE zostaną dołączone do releasu

Budowane platformy:
- **Windows** (windows-latest) → `InvestmentAdvisor-windows-x86_64.exe`
- **Linux** (ubuntu-latest) → `InvestmentAdvisor-linux-x86_64`

---

## Licencja

Projekt prywatny.
