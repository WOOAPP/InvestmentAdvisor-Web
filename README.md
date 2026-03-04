# Investment Advisor

Desktopowa aplikacja do analizy rynków finansowych z AI. Pobiera dane rynkowe, wiadomości i treści ze stron, a następnie generuje szczegółowe raporty inwestycyjne za pomocą modeli AI (Anthropic Claude / OpenAI GPT / OpenRouter). Interfejs w Tkinter z motywem Catppuccin Mocha.

## Pobieranie

Gotowe pliki wykonywalne — **nie wymagają Pythona ani instalacji**:

| System | Plik |
|--------|------|
| **Windows** | [InvestmentAdvisor-windows-x86_64.exe](https://github.com/WOOAPP/InvestmentAdvisor/releases/latest) |
| **Linux** | [InvestmentAdvisor-linux-x86_64](https://github.com/WOOAPP/InvestmentAdvisor/releases/latest) |

> Na Windows może pojawić się ostrzeżenie SmartScreen — kliknij **"More info"** → **"Run anyway"**.

## Screenshoty

Po uruchomieniu aplikacja tworzy okno z zakładkami: Dashboard, Wykresy, Portfel, Kalendarz, Chat, Historia, Ustawienia.

## Funkcje

### Dashboard
- Kafelki z cenami instrumentów w czasie rzeczywistym (auto-odświeżanie co sekundę)
- Mini wykresy (sparklines) z wyborem zakresu: 1m / 15m / 1h / 6h / 24h
- Miernik ryzyka rynkowego (gauge) wyliczany z ostatniego raportu AI
- Podgląd ostatniego raportu z renderowaniem Markdown
- Pasek informacyjny: model AI, tokeny, koszt analizy (USD + PLN)

### Analiza AI
- Generowanie raportów przez: **Anthropic** (Claude Opus / Sonnet / Haiku), **OpenAI** (GPT-4.1, o3, o4-mini), **OpenRouter** (dowolny model)
- Struktura raportu: News dnia → Sytuacja per region → Porównanie trendów → Implikacje → Scenariusze + ryzyko
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
- Dane z ForexFactory (format JSON)
- Dwa tryby: **"Od dziś"** (nadchodzące wydarzenia) / **"Cały tydzień"**
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
- Otwieranie w osobnym oknie (popup)

### Trend makro
- Pipeline: Newsdata.io → klasyfikacja regionalna/tematyczna → scoring → top news dnia
- Porównanie trendów: 24h vs 7d vs 30d vs 90d
- Automatyczne wykrywanie zmian sentymentu, anomalii i punktów zwrotnych

### Bezpieczeństwo
- Ochrona SSRF: walidacja URL przed każdym żądaniem scrapera (schemat, IP, DNS, allowlist)
- Maskowanie kluczy API w logach i UI
- Zmienne środowiskowe mają priorytet — klucze z ENV nie są zapisywane do pliku
- Limity scrapera: max 20 URL, max 2 MB, max 3 przekierowania, timeout 8s/15s
- HTTP retry z backoff na 429/5xx
- Sekcja ustawień chroniona hasłem

## Źródła danych rynkowych

| Źródło | Instrumenty | Uwagi |
|--------|-------------|-------|
| **yfinance** | Akcje, indeksy, forex, surowce | Domyślne źródło |
| **CoinGecko** | Kryptowaluty | Rate limit 2.5s, cache 10 min |
| **Stooq** | Instrumenty polskie (WIG, mWIG40) | CSV API |

## Wymagania (uruchomienie ze źródeł)

- Python 3.10+
- System z Tkinter (wbudowane w większość dystrybucji Pythona)

```bash
pip install anthropic openai yfinance requests beautifulsoup4 matplotlib pandas schedule fpdf2
```

## Konfiguracja kluczy API

Klucze API ustawia się jako **zmienne środowiskowe** (zalecane) lub w UI (Ustawienia → Klucze API).

Zmienne środowiskowe mają priorytet nad `data/config.json`.

| Zmienna | Opis | Wymagane? |
|---------|------|-----------|
| `ANTHROPIC_API_KEY` | Klucz Anthropic (Claude) | Wymagane dla Anthropic |
| `OPENAI_API_KEY` | Klucz OpenAI | Wymagane dla OpenAI |
| `OPENROUTER_API_KEY` | Klucz OpenRouter | Wymagane dla OpenRouter |
| `NEWSDATA_KEY` | Klucz Newsdata.io (wiadomości) | Opcjonalne (wzbogaca raporty) |

### Przykład

```bash
export ANTHROPIC_API_KEY="sk-ant-xxxx..."
export NEWSDATA_KEY="pub_xxxx..."
python main.py
```

Lub utwórz plik `.env` i załaduj go `source .env` przed uruchomieniem.

## Uruchomienie

```bash
python main.py
```

Auto-analiza (tryb cron):
```bash
python main.py --auto-analysis
```

## Testy

```bash
python -m unittest discover tests/ -v
```

242+ testów obejmujących: AI engine, wykresy, bazę danych, klient HTTP, dane rynkowe, pipeline newsów, walidację URL, helpery UI.

## Struktura projektu

```
InvestmentAdvisor/
├── main.py                  # Aplikacja Tkinter (GUI)
├── config.py                # Konfiguracja, zmienne środowiskowe
├── constants.py             # 73 parametry tuningowe
├── modules/
│   ├── ai_engine.py         # Dispatch: Anthropic / OpenAI / OpenRouter
│   ├── market_data.py       # yfinance, CoinGecko, Stooq
│   ├── database.py          # SQLite CRUD
│   ├── charts.py            # Matplotlib w Tkinter
│   ├── scraper.py           # Równoległy scraper z walidacją SSRF
│   ├── http_client.py       # HTTP z retry i backoff
│   ├── url_validator.py     # Ochrona SSRF
│   ├── calendar_data.py     # Kalendarz ekonomiczny (ForexFactory)
│   ├── news_store.py        # Newsdata.io, deduplikacja
│   ├── news_classifier.py   # Klasyfikacja region/temat (regex)
│   ├── news_of_day.py       # Scoring najważniejszych newsów
│   ├── macro_trend.py       # Orkiestrator trendu makro
│   ├── trend_narrative.py   # Porównanie okien czasowych
│   ├── openai_pricing.py    # Kalkulator kosztów LLM
│   ├── ui_helpers.py        # Markdown renderer, BusySpinner
│   └── exceptions.py        # Wyjątki: DataFetchError, AIProviderError
├── tests/                   # 13 plików testowych, 242+ test cases
└── data/
    ├── config.json           # Konfiguracja użytkownika (nie wersjonowane)
    └── advisor.db            # Baza SQLite (nie wersjonowane)
```

## Licencja

Projekt prywatny.
