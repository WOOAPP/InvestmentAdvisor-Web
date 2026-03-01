# Investment Advisor

Osobisty asystent inwestycyjny z analizą rynkową AI, wykresami i czatem.

## Wymagania

- Python 3.10+
- Zależności: `pip install -r requirements.txt` (lub indywidualnie: `yfinance`, `requests`, `beautifulsoup4`, `anthropic`, `openai`, `matplotlib`, `schedule`, `pandas`)

## Konfiguracja kluczy API (zmienne środowiskowe)

Klucze API można ustawić jako zmienne środowiskowe (**zalecane**) lub w UI aplikacji (Ustawienia → Klucze API).

**Zmienne środowiskowe mają priorytet** nad wartościami z `data/config.json`.

| Zmienna              | Opis                        | Wymagane? |
|----------------------|-----------------------------|-----------|
| `NEWSAPI_KEY`        | Klucz NewsAPI (wiadomości)  | Opcjonalne |
| `OPENAI_API_KEY`     | Klucz OpenAI                | Zależne od providera |
| `ANTHROPIC_API_KEY`  | Klucz Anthropic (Claude)    | Zależne od providera |
| `OPENROUTER_API_KEY` | Klucz OpenRouter             | Zależne od providera |

### Przykład (.env / shell)

```bash
export NEWSAPI_KEY="pub_xxxx..."
export OPENAI_API_KEY="sk-proj-xxxx..."
# lub
export ANTHROPIC_API_KEY="sk-ant-xxxx..."
```

Alternatywnie utwórz plik `.env` (dodany do `.gitignore`) i załaduj go przez `source .env` przed uruchomieniem.

## Uruchomienie

```bash
python main.py
```

## Bezpieczeństwo

- **Klucze API**: zmienne środowiskowe > config.json; klucze z env nie są zapisywane do pliku.
- **Maskowanie**: w UI klucze wyświetlane są jako `sk-p************ (ENV)`.
- **Scraper (SSRF)**: walidacja URL — tylko http/https, blokada adresów prywatnych/loopback/link-local, sprawdzanie DNS resolve.
- **Allowlist domen**: w `data/config.json` → `trusted_domains` — scraper pobiera treść tylko z zaufanych domen.
- **Limity**: max 20 URL na analizę, max 3 przekierowania, max 2 MB odpowiedzi, timeout 8s/15s (connect/read).
- **HTTP retry**: wspólny klient z retry (2 próby) i backoff na 429/5xx.
- **Testy**: `python -m unittest tests.test_url_validator -v`
