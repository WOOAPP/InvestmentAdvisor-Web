# InvestmentAdvisor – CLAUDE.md

## Project Overview

**InvestmentAdvisor** is a Python desktop application for financial market analysis, currently undergoing migration to a web application.
It fetches real-time market data, news (Newsdata.io), and web-scraped content, then sends everything
to AI models (Anthropic / OpenAI / OpenRouter) which generate detailed investment reports.
The GUI is currently built with Tkinter using the Catppuccin Mocha dark theme.

**Current status:** Desktop (Tkinter) application — web migration planned.

---

## Running the Application

```bash
python main.py
```

Requires Python 3.10+. On first run the app creates `data/advisor.db` (SQLite) and `data/config.json`.

Auto-analysis mode (launched by cron):
```bash
python main.py --auto-analysis
```

### Installing Dependencies

```bash
pip install anthropic openai yfinance requests beautifulsoup4 matplotlib pandas schedule fpdf2
```

### Running Tests

```bash
python -m unittest discover tests/ -v
```

There are 13 test files with 242+ test cases covering core modules.

---

## Project Structure

```
InvestmentAdvisor/
├── main.py                    # Tkinter application (class InvestmentAdvisor, ~4550 LOC)
├── config.py                  # Config load/save, env overrides, default instruments & prompts
├── constants.py               # 73 centralized tuning parameters (timeouts, limits, weights)
├── CLAUDE.md                  # This file
├── data/
│   ├── config.json            # User config (API keys, instruments) – not versioned
│   ├── advisor.db             # SQLite database – not versioned
│   └── llm_pricing_cache.json # Cached LLM pricing – auto-generated
├── modules/
│   ├── ai_engine.py           # AI provider dispatch (Anthropic / OpenAI / OpenRouter)
│   ├── market_data.py         # Market data fetching (yfinance, CoinGecko, Stooq, Newsdata.io)
│   ├── database.py            # SQLite CRUD – reports, snapshots, alerts, portfolio, profiles
│   ├── charts.py              # Matplotlib charts embedded in Tkinter (price, volume, risk gauge)
│   ├── scraper.py             # Parallel web scraper with URL validation (BeautifulSoup)
│   ├── http_client.py         # Shared HTTP session with retry, backoff, URL masking
│   ├── url_validator.py       # SSRF protection: scheme/IP/DNS checks + domain allowlist
│   ├── calendar_data.py       # Economic calendar (ForexFactory JSON feed)
│   ├── news_store.py          # News fetching (Newsdata.io), deduplication, SQLite storage
│   ├── news_classifier.py     # Deterministic region/topic classification (regex, no ML)
│   ├── news_of_day.py         # Scoring engine to select most impactful news
│   ├── macro_trend.py         # Macro-trend orchestrator: news → classify → trend → LLM payload
│   ├── trend_narrative.py     # Trend aggregation & window comparison (24h vs 7d/30d/90d)
│   ├── openai_pricing.py      # LLM cost calculation with 3-level cache (memory/disk/web)
│   ├── ui_helpers.py          # Markdown renderer for Tkinter, BusySpinner, click-to-focus
│   └── exceptions.py          # Custom exceptions: DataFetchError, AIProviderError, ScraperError
└── tests/
    ├── test_ai_engine.py      # Provider dispatch, token counting, prompt builders
    ├── test_charts.py         # Bar width, vol colors, x-axis formatting, risk extraction
    ├── test_database.py       # Full CRUD, migrations, isolation via temp DB
    ├── test_http_client.py    # URL masking for logs
    ├── test_macro_trend.py    # Payload slimming, LLM formatting
    ├── test_market_data.py    # yfinance/CoinGecko/Stooq, FX cache, formatting
    ├── test_news_classifier.py # Region/topic classification, priority order
    ├── test_news_of_day.py    # Scoring components, selection, justification
    ├── test_news_store.py     # Dedup, window fetching, auth error fail-fast
    ├── test_trend_narrative.py # Aggregation, window comparison, signals
    ├── test_ui_helpers.py     # Markdown rendering, spinner lifecycle
    └── test_url_validator.py  # SSRF prevention, IP blocking, allowlist (28 tests)
```

---

## Architecture & Data Flow

```
User clicks "Uruchom Analize"
        │
        ├── market_data.py ──→ yfinance / CoinGecko / Stooq
        │       └── http_client.py (safe_get with retry)
        │
        ├── macro_trend.py ──→ news_store.py ──→ Newsdata.io API
        │       ├── news_classifier.py (region/topic tagging)
        │       ├── news_of_day.py (scoring → top news)
        │       └── trend_narrative.py (7d/30d/90d comparisons)
        │
        ├── scraper.py ──→ url_validator.py (SSRF check) ──→ HTTP fetch
        │
        └── ai_engine.py ──→ Anthropic / OpenAI / OpenRouter API
                │
                └── Report saved to database.py → SQLite
```

All heavy I/O runs in daemon threads; UI updates via `self.after(0, callback)`.

---

## Business Logic Modules (backend-ready)

These modules contain **zero Tkinter/UI dependencies** and can be reused directly as web backend:

| Module | Responsibility | Web-ready? |
|--------|---------------|------------|
| `ai_engine.py` | AI provider dispatch, prompt building, chat | Yes |
| `market_data.py` | yfinance/CoinGecko/Stooq data fetching | Yes |
| `database.py` | SQLite CRUD (reports, portfolio, alerts, profiles) | Yes (consider PostgreSQL migration) |
| `scraper.py` | Parallel web scraping with SSRF protection | Yes |
| `http_client.py` | HTTP session with retry/backoff | Yes |
| `url_validator.py` | SSRF protection for scraper | Yes |
| `calendar_data.py` | Economic calendar from ForexFactory | Yes |
| `news_store.py` | News fetching, dedup, SQLite storage | Yes |
| `news_classifier.py` | Regex-based region/topic classification | Yes |
| `news_of_day.py` | News scoring/selection engine | Yes |
| `macro_trend.py` | Macro-trend orchestrator | Yes |
| `trend_narrative.py` | Trend aggregation & comparison | Yes |
| `openai_pricing.py` | LLM cost calculation | Yes |
| `config.py` | Config load/save, env overrides | Needs adaptation for web (per-user config) |
| `constants.py` | Tuning parameters | Yes |
| `exceptions.py` | Custom exceptions | Yes |

**UI-coupled modules (must be replaced for web):**

| Module | Why it needs replacement |
|--------|------------------------|
| `main.py` (~4550 LOC) | Entire Tkinter GUI — one monolithic class |
| `charts.py` | Matplotlib embedded in Tkinter (FigureCanvasTkAgg) |
| `ui_helpers.py` | Tkinter-specific markdown renderer, spinners |

---

## Configuration (`data/config.json`)

Auto-created on first run. Key fields:

| Field | Description |
|-------|-------------|
| `api_keys.anthropic` | Anthropic API key |
| `api_keys.openai` | OpenAI API key |
| `api_keys.openrouter` | OpenRouter API key |
| `api_keys.newsdata` | Newsdata.io API key |
| `ai_provider` | `"anthropic"`, `"openai"`, or `"openrouter"` |
| `ai_model` | e.g. `"claude-opus-4-6"`, `"gpt-4.1"`, `"openai/gpt-4o"` |
| `chat_provider` / `chat_model` | Separate provider/model for chat |
| `instruments` | `[{symbol, name, category, source}]` |
| `sources` | URLs for web scraping |
| `trusted_domains` | Domain allowlist for scraper (80+ defaults) |
| `prompt` | System prompt for analysis |
| `chat_prompt` | System prompt for chat |
| `schedule.enabled` | Enable automatic analysis (bool) |
| `schedule.times` | Times e.g. `["08:00", "16:00"]` |

### Environment Variable Overrides (priority over config file)

| Env Variable | Overrides |
|---|---|
| `ANTHROPIC_API_KEY` | `api_keys.anthropic` |
| `OPENAI_API_KEY` | `api_keys.openai` |
| `OPENROUTER_API_KEY` | `api_keys.openrouter` |
| `NEWSDATA_KEY` | `api_keys.newsdata` |

Keys loaded from env are never written back to `config.json`.

### Available AI Models

**Anthropic:** `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`

**OpenAI:** `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `o3`, `o3-mini`, `o4-mini`, `o1`, `o1-preview`, `o1-mini`

**OpenRouter:** Any model available on OpenRouter via `provider/model` format (e.g. `openai/gpt-4o`).

---

## AI Provider Logic

Provider dispatch in `modules/ai_engine.py`:

1. **`_call_provider(provider, ...)`** — unified entry point
   - `"anthropic"` → uses `anthropic.Anthropic` client
   - `"openai"` → uses `openai.OpenAI` client
   - `"openrouter"` → uses `openai.OpenAI` client with `base_url="https://openrouter.ai/api/v1"`
2. **Token kwarg handling** — OpenAI models use `max_tokens` or `max_completion_tokens` depending on model; auto-retries with swapped kwarg on `BadRequestError`
3. **`run_analysis()`** — builds prompt from market data + news + scraped text, calls provider
   - Uses macro-trend prompt if macro data available, otherwise falls back to legacy prompt
4. **`run_chat()`** — multi-turn chat with conversation history
5. **Cost tracking** — `openai_pricing.py` calculates USD cost per call; displayed in UI with PLN conversion

---

## Market Data Sources

| Source | Module Function | Data |
|--------|-----------------|------|
| `yfinance` | `get_yfinance_data()` | Stocks, indices, forex, commodities (default) |
| `coingecko` | `get_coingecko_data()` | Cryptocurrencies (rate-limited: 2.5s interval) |
| `stooq` | `get_stooq_data()` | Polish instruments (CSV API) |

Batching: CoinGecko coins are fetched in a single batch API call when possible.

Caching:
- CoinGecko prices: 10 min TTL (in-memory, thread-safe)
- CoinGecko sparklines: 1 hour TTL
- FX rates: configurable TTL (`FX_CACHE_TTL` in constants)

---

## Database (SQLite)

File: `data/advisor.db` (not versioned). Auto-migrated on startup.

| Table | Contents |
|-------|----------|
| `reports` | AI reports (provider, model, analysis, risk level, token usage) |
| `market_snapshots` | Price history for instruments |
| `alerts` | Price alerts (seen/unseen) |
| `portfolio` | Portfolio positions (symbol, quantity, buy price, currency, FX rate) |
| `instrument_profiles` | Cached AI-generated instrument profiles |
| `news_items` | Stored news articles with hash deduplication (5 indexes) |

All DB access is thread-safe via `threading.RLock`.

---

## Security Mechanisms

### SSRF Protection (`modules/url_validator.py`)
Applied to all scraper URLs before any HTTP request:
1. **Scheme check** — only `http` / `https` allowed
2. **Literal IP block** — private, loopback, reserved, link-local, multicast ranges
3. **Known hostname block** — `localhost`, `ip6-localhost`, etc.
4. **DNS resolution check** — resolves hostname, blocks if IP is private/loopback
5. **Domain allowlist** — if `trusted_domains` configured, only allowlisted domains pass (supports subdomains)

### HTTP Client (`modules/http_client.py`)
- Automatic retry with exponential backoff on 429/500/502/503/504
- Configurable timeouts (connect: 8s, read: 15s)
- URL masking in logs — `apiKey`, `api_key`, `token`, `secret`, `password` params are masked
- Singleton session with thread-safe initialization

### Scraper (`modules/scraper.py`)
- URL validation via `url_validator` before any request
- Response size limit (2 MB)
- Read timeout enforcement during streaming
- Max 3 redirects
- Max 20 URLs per scrape run
- Parallel scraping with ThreadPoolExecutor (max 6 workers)

### API Keys
- Environment variables take priority over config file
- Keys from env are never saved to `config.json`
- `mask_key()` in `config.py` masks keys for UI display
- Settings tab is password-protected (prompts section)

### .gitignore
`data/config.json` and `data/advisor.db` are excluded from version control.

---

## Known Weak Spots / Areas Needing Attention

1. **`main.py` is 4550+ LOC** — the entire UI lives in one class. Should be split into tab-specific modules.
2. **Synchronous AI calls** — `run_analysis()` and `run_chat()` block their worker thread; no timeout parameter passed to API clients.
3. **Hardcoded password** — `_SETTINGS_PASSWORD = "666"` in `main.py` (plaintext, not hashed).
4. **SSRF TOCTOU risk** — DNS is validated at check time, but the actual HTTP request happens later (hostname could resolve differently).
5. **No SSRF on non-scraper HTTP** — `market_data.py` calls CoinGecko/Stooq URLs with user-provided symbols without URL validation.
6. **Matplotlib thread safety** — charts are created on the main thread but `fetch_chart_data()` inside `create_price_chart()` does blocking I/O.
7. **Duplicate news classification** — `macro_trend.py` calls `classify_articles()` 5 times (once on raw, then again on each DB query result).
8. **No retry on yfinance/CoinGecko** — HTTP retry exists for scraper via `http_client`, but yfinance uses its own HTTP and CoinGecko uses `safe_get` (which does retry).
9. **`news_store.py` lazy init** — `_ensure_table()` creates the DB file as a side effect on first DB access.
10. **Web pricing scrape is brittle** — `openai_pricing.py` tries to scrape the OpenAI pricing page (JS SPA); this always fails. Hardcoded fallback covers it.
11. **Single-user architecture** — `data/config.json` is global, not per-user. Web migration needs user accounts and per-user config.
12. **No auth system** — desktop app has no login. Web version requires proper authentication.

---

## Coding Conventions

- **UI and prompt language:** Polish
- **Code comments:** mixed Polish/English — preserve existing style per file
- **Error pattern:** functions returning external data use `{"error": "..."}` dicts on failure
- **Threading:** all background work uses `threading.Thread(daemon=True)`, UI updates via `self.after(0, callback)`
- **Constants:** tuning parameters centralized in `constants.py` (73 values)
- **Thread safety:** global caches use `threading.Lock` or `threading.RLock`
- **Style:** straightforward, minimal abstraction; UI logic in `main.py`, business logic in `modules/`
- **Custom exceptions** defined in `modules/exceptions.py` but not widely used yet (most code catches broad exceptions)

---

## Visual Theme

Catppuccin Mocha palette — colors defined in `main.py` and `modules/charts.py`:

```python
BG     = "#1e1e2e"   # main background
BG2    = "#181825"   # secondary background
FG     = "#cdd6f4"   # text
ACCENT = "#89b4fa"   # blue accent
GREEN  = "#a6e3a1"
RED    = "#f38ba8"
YELLOW = "#f9e2af"
GRAY   = "#313244"
```

Colors are also duplicated in `modules/ui_helpers.py` (prefixed with `_`).

---

## Common Development Tasks

### Add a New Market Data Source
1. Add `get_XYZ_data(symbol, name)` in `modules/market_data.py`
2. Handle the new `"source"` value in `get_all_instruments()`
3. Extend `format_market_summary()` if needed
4. Add chart support in `charts.py:fetch_chart_data()` if applicable

### Add a New UI Tab
1. In `main.py`, method `_build_ui()` manages `ttk.Notebook`
2. Add `_build_XXX_tab(nb)` following existing patterns

### Change the AI Model
Edit `data/config.json` fields `ai_model` / `chat_model`, or change in UI (Settings tab).

### Add a New AI Provider
1. Add branch in `_call_provider()` in `modules/ai_engine.py`
2. Add entry in `get_available_models()` and `_PROVIDER_DEFAULTS`
3. Add env variable mapping in `config.py:_apply_env_overrides()`

### Add a New Tuning Parameter
Add the constant to `constants.py` and import it where needed. Avoid hardcoding magic numbers.

---

## What to Be Careful About Before Making Changes

1. **Thread safety** — any global/shared state must be protected by locks. UI operations must run on the main thread (use `self.after()`).
2. **`main.py` size** — the file is huge; changes here risk merge conflicts. Keep edits minimal and targeted.
3. **API key safety** — never log, print, or commit API keys. Use `mask_key()` for display. Use env vars.
4. **Matplotlib** — not thread-safe. All figure creation/modification must happen on the main thread. Always close figures to avoid memory leaks.
5. **Import side effects** — `news_store.py` creates DB tables on first access. `database.py:init_db()` is called explicitly but runs migrations every time.
6. **Config schema** — adding fields to config requires backward-compatible defaults in `load_config()`.
7. **Prompt changes** — system prompts are stored in `config.json` and are large (900+ lines). Users may have customized them. Don't overwrite silently.
8. **Test suite** — run `python -m unittest discover tests/ -v` before pushing. Tests cover AI engine, charts, database, HTTP client, market data, news pipeline, URL validator, and UI helpers.

---

## Web Migration Plan (Desktop → Web)

### Target Architecture

```
Browser (React + TypeScript)
        │
        ├── REST API ──→ FastAPI (Python backend)
        │                   ├── modules/ (reused from desktop)
        │                   ├── auth (JWT + bcrypt)
        │                   └── WebSocket for real-time prices
        │
        └── Static files served by Nginx
                │
                └── Docker Compose (Nginx + FastAPI + PostgreSQL)
```

### Stack Decisions

- **Frontend:** React + TypeScript + Vite (rich ecosystem for dashboards, charts via Recharts/Lightweight Charts)
- **Backend:** FastAPI (async, Python — direct reuse of existing modules)
- **Database:** PostgreSQL (replaces SQLite for multi-user, concurrent access)
- **Charts:** Lightweight Charts (TradingView) or Recharts (replaces Matplotlib)
- **Communication:** REST API + WebSocket (for live price updates)
- **Deployment:** Docker Compose + Nginx reverse proxy on VPS

### What Can Be Reused Directly

All `modules/` files except `charts.py` and `ui_helpers.py` — they are UI-framework-independent.

### What Must Be Rewritten

1. `main.py` — entire Tkinter GUI → React frontend + FastAPI endpoints
2. `charts.py` — Matplotlib/Tkinter → Lightweight Charts (JS) or server-side chart API
3. `ui_helpers.py` — Tkinter markdown renderer → React markdown component
4. `config.py` — global config → per-user config stored in PostgreSQL
5. Auth system — from scratch (JWT, bcrypt, user registration)

See the full migration plan in the PR description.
