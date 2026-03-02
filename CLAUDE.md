# InvestmentAdvisor – CLAUDE.md

## Opis projektu

**InvestmentAdvisor** to desktopowa aplikacja do analizy rynków finansowych napisana w Pythonie.
Pobiera dane rynkowe w czasie rzeczywistym, pobiera newsy i wysyła je do modeli AI (Anthropic / OpenAI),
które generują szczegółowe raporty inwestycyjne. Interfejs graficzny oparty na Tkinter z ciemnym motywem Catppuccin Mocha.

---

## Uruchamianie aplikacji

```bash
python main.py
```

Wymagany Python 3.10+. Przy pierwszym uruchomieniu aplikacja tworzy plik `data/advisor.db` (SQLite).

### Instalacja zależności

```bash
pip install anthropic openai yfinance requests beautifulsoup4 matplotlib pandas schedule
```

---

## Struktura projektu

```
InvestmentAdvisor/
├── main.py                 # Główna aplikacja Tkinter (klasa InvestmentAdvisor)
├── config.py               # Ładowanie/zapis konfiguracji, domyślne instrumenty
├── data/
│   ├── config.json         # Konfiguracja użytkownika (klucze API, instrumenty)
│   └── advisor.db          # Baza SQLite (nie wersjonowana)
└── modules/
    ├── ai_engine.py        # Integracja z Anthropic i OpenAI
    ├── market_data.py      # Pobieranie danych (yfinance, CoinGecko, Stooq)
    ├── database.py         # CRUD SQLite – raporty, snapshoty, alerty, portfel
    ├── charts.py           # Wykresy Matplotlib osadzone w Tkinter
    ├── scraper.py          # Web scraper (BeautifulSoup)
    └── calendar_data.py    # Dane kalendarza ekonomicznego
```

---

## Konfiguracja (`data/config.json`)

Plik JSON tworzony automatycznie przy pierwszym uruchomieniu. Kluczowe pola:

| Pole | Opis |
|------|------|
| `api_keys.anthropic` | Klucz API Anthropic |
| `api_keys.openai` | Klucz API OpenAI |
| `api_keys.newsapi` | Klucz API NewsAPI.org |
| `ai_provider` | `"anthropic"` lub `"openai"` |
| `ai_model` | Np. `"claude-opus-4-6"` lub `"gpt-4o"` |
| `instruments` | Lista instrumentów: `[{symbol, name, category, source}]` |
| `sources` | Lista URL-i do scrapowania |
| `prompt` | System prompt wysyłany do modelu AI |
| `schedule.enabled` | Automatyczne analizy (bool) |
| `schedule.times` | Lista godzin np. `["08:00", "16:00"]` |

### Dostępne modele

**Anthropic:** `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`

**OpenAI:** `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `o1-preview`

---

## Źródła danych rynkowych

| Source | Użycie |
|--------|--------|
| `yfinance` | Akcje, indeksy, forex, surowce (domyślne) |
| `coingecko` | Kryptowaluty (Bitcoin, Ethereum itp.) |
| `stooq` | Alternatywa dla polskich instrumentów |

Instrument definiuje się przez pole `"source"` w liście `instruments` w config.

---

## Baza danych SQLite

Plik: `data/advisor.db` (poza kontrolą wersji).

| Tabela | Zawartość |
|--------|-----------|
| `reports` | Raporty AI (provider, model, analiza, poziom ryzyka) |
| `market_snapshots` | Historia cen instrumentów |
| `alerts` | Alerty cenowe |
| `portfolio` | Pozycje portfela (symbol, ilość, cena zakupu) |

---

## Motyw wizualny

Aplikacja używa palety **Catppuccin Mocha** – kolory zdefiniowane na górze `main.py` i `modules/charts.py`:

```python
BG     = "#1e1e2e"   # tło główne
BG2    = "#181825"   # tło wtórne
FG     = "#cdd6f4"   # tekst
ACCENT = "#89b4fa"   # niebieski akcent
GREEN  = "#a6e3a1"
RED    = "#f38ba8"
YELLOW = "#f9e2af"
GRAY   = "#313244"
```

---

## Konwencje kodowania

- **Język UI i promptów:** polski
- **Komentarze w kodzie:** polski lub angielski (mieszane – zachowaj styl pliku)
- **Brak testów automatycznych** – aplikacja desktopowa, testowanie manualne
- **Obsługa błędów:** każda funkcja pobierająca dane zwraca dict z kluczem `"error"` przy niepowodzeniu
- **Styl:** prosty, bez nadmiarowych abstrakcji; logika UI w `main.py`, logika biznesowa w `modules/`

---

## Ostrzeżenie bezpieczeństwa

> `data/config.json` zawiera klucze API w plaintext i **nie jest** w `.gitignore`.
> **Nie commituj tego pliku** z prawdziwymi kluczami do repozytorium.
> Dodaj do `.gitignore`:
> ```
> data/config.json
> ```
> Klucze API przechowuj w zmiennych środowiskowych lub pliku lokalnym poza repo.

---

## Typowe zadania deweloperskie

### Dodanie nowego źródła danych
1. Dodaj funkcję `get_XYZ_data(symbol, name)` w `modules/market_data.py`
2. Obsłuż nową wartość `"source"` w `get_all_instruments()`
3. Ewentualnie rozszerz kategoryzację w `format_market_summary()`

### Dodanie nowej zakładki UI
1. W `main.py` metoda `_build_ui()` zarządza `ttk.Notebook`
2. Dodaj metodę `_build_XXX_tab(nb)` wzorując się na istniejących

### Zmiana modelu AI
Edytuj `data/config.json` lub zmień w UI (zakładka Ustawienia) – pole `ai_model`.

### Dodanie nowego dostawcy AI
1. Dodaj funkcję `_run_XYZ(config, prompt, message)` w `modules/ai_engine.py`
2. Dodaj gałąź w `run_analysis()` i wpis w `get_available_models()`
