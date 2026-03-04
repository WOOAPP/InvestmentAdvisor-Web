# Investment Advisor

Osobisty asystent inwestycyjny z analizą rynkową AI, wykresami i czatem.

## Pobieranie

Gotowe pliki wykonywalne (nie wymagają Pythona):

| System | Plik |
|--------|------|
| **Windows** | [InvestmentAdvisor-windows-x86_64.exe](https://github.com/WOOAPP/InvestmentAdvisor/releases/latest) |
| **Linux** | [InvestmentAdvisor-linux-x86_64](https://github.com/WOOAPP/InvestmentAdvisor/releases/latest) |

Na Windows może pojawić się ostrzeżenie SmartScreen — kliknij **"Uruchom mimo to"** / **"More info" → "Run anyway"**.

## Funkcje

- **Analiza AI** — raporty generowane przez Claude, GPT-4, OpenRouter (wybór modelu)
- **Dashboard** — kafelki z cenami, mini wykresy (sparklines), miernik ryzyka
- **Wykresy** — interaktywne wykresy cenowe z MA20/MA50, wolumen, porównanie instrumentów
- **Kalendarz ekonomiczny** — widok 7 dni do przodu, bieżący i następny tydzień
- **Portfel** — 3 zakładki: obserwowane, gra na wzrosty (long), gra na spadki (short)
- **Chat AI** — rozmowa z modelem z pełnym kontekstem portfela i ostatniego raportu
- **Trend makro** — analiza newsów, klasyfikacja regionalna, porównanie trendów 24h/7d/30d/90d
- **Auto-analiza** — harmonogram automatycznych analiz (cron / wbudowany scheduler)
- **Eksport PDF** — raport w formacie PDF

## Wymagania (uruchomienie ze źródeł)

- Python 3.10+
- Zależności: `pip install anthropic openai yfinance requests beautifulsoup4 matplotlib pandas schedule fpdf2`

## Konfiguracja kluczy API

Klucze API można ustawić jako zmienne środowiskowe (**zalecane**) lub w UI aplikacji (Ustawienia → Klucze API).

**Zmienne środowiskowe mają priorytet** nad wartościami z `data/config.json`.

| Zmienna              | Opis                        | Wymagane? |
|----------------------|-----------------------------|-----------|
| `NEWSDATA_KEY`       | Klucz Newsdata.io (wiadomości) | Opcjonalne |
| `OPENAI_API_KEY`     | Klucz OpenAI                | Zależne od providera |
| `ANTHROPIC_API_KEY`  | Klucz Anthropic (Claude)    | Zależne od providera |
| `OPENROUTER_API_KEY` | Klucz OpenRouter            | Zależne od providera |

### Przykład (.env / shell)

```bash
export NEWSDATA_KEY="pub_xxxx..."
export OPENAI_API_KEY="sk-proj-xxxx..."
# lub
export ANTHROPIC_API_KEY="sk-ant-xxxx..."
```

## Uruchomienie

```bash
python main.py
```

Auto-analiza (cron):
```bash
python main.py --auto-analysis
```

## Testy

```bash
python -m unittest discover tests/ -v
```

## Bezpieczeństwo

- **Klucze API**: zmienne środowiskowe > config.json; klucze z env nie są zapisywane do pliku.
- **Maskowanie**: w UI klucze wyświetlane są jako `sk-p************ (ENV)`.
- **Scraper (SSRF)**: walidacja URL — tylko http/https, blokada adresów prywatnych/loopback/link-local, sprawdzanie DNS resolve.
- **Allowlist domen**: w `data/config.json` → `trusted_domains` — scraper pobiera treść tylko z zaufanych domen.
- **Limity**: max 20 URL na analizę, max 3 przekierowania, max 2 MB odpowiedzi, timeout 8s/15s (connect/read).
- **HTTP retry**: wspólny klient z retry (2 próby) i backoff na 429/5xx.
