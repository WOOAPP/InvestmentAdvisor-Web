# InvestmentAdvisor – CLAUDE.md

## Project Overview

**InvestmentAdvisor** is a financial market analysis platform that fetches real-time market data, news (Newsdata.io), and web-scraped content, then sends everything to AI models (Anthropic / OpenAI / OpenRouter) which generate detailed investment reports.

**Architecture:** Web application (FastAPI + React) with legacy desktop app (Tkinter) still present.
**Current status:** Web v1.0 deployed and live at `http://iadvisors-web.rafaldebski.com`. Desktop app (`main.py`) preserved for reference.

---

## Running the Application

### Web — Development (Docker Compose)
```bash
cp .env.example .env          # Edit with your settings
docker compose up --build      # PostgreSQL + FastAPI + Nginx (ports: 5432, 8000, 80)
cd frontend && npm run dev     # Vite dev server at localhost:5173
```

### Web — Development (without Docker)
```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn backend.app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

### Legacy Desktop Application
```bash
pip install anthropic openai yfinance requests beautifulsoup4 matplotlib pandas schedule fpdf2
python main.py
```

### Production (Hetzner VPS)
```
Server:  65.108.211.80 (Hetzner CX23, Ubuntu 24.04, Helsinki)
Domain:  iadvisors-web.rafaldebski.com (GoDaddy DNS → A record)
URL:     http://iadvisors-web.rafaldebski.com
Path:    /opt/InvestmentAdvisor-Web
```

Deploy workflow:
```bash
# 1. Local: commit & push
git add . && git commit -m "description" && git push origin main

# 2. Server (ssh root@65.108.211.80):
cd /opt/InvestmentAdvisor-Web && git pull
cd frontend && npm run build && cd ..
docker compose up --build -d
docker compose exec backend alembic -c /app/backend/alembic.ini upgrade head  # if DB changes
```

### Running Tests (desktop modules)
```bash
python -m unittest discover tests/ -v
```
13 test files, 242+ test cases covering core modules.

---

## Project Structure

```
InvestmentAdvisor-Web/
├── CLAUDE.md
├── docker-compose.yml         # PostgreSQL + FastAPI + Nginx
├── .env.example               # All env config options
├── nginx/default.conf         # Reverse proxy config
│
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI entry point, Alembic on startup, CORS
│   │   ├── api/               # Route handlers
│   │   │   ├── auth.py        # Register, login, refresh, me
│   │   │   ├── market.py      # Instrument prices, sparklines
│   │   │   ├── reports.py     # CRUD + run analysis
│   │   │   ├── portfolio.py   # Positions CRUD
│   │   │   ├── chat.py        # AI chat
│   │   │   ├── settings.py    # User config CRUD
│   │   │   ├── calendar.py    # Economic calendar
│   │   │   ├── stats.py       # Token usage stats
│   │   │   └── news.py        # News feed
│   │   ├── core/
│   │   │   ├── config.py      # Pydantic Settings (from env/.env)
│   │   │   ├── database.py    # Async SQLAlchemy engine + session
│   │   │   ├── security.py    # JWT creation/verification, bcrypt
│   │   │   └── deps.py        # FastAPI dependencies (get_db, get_current_user)
│   │   ├── models/            # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── report.py
│   │   │   ├── portfolio.py
│   │   │   ├── alert.py
│   │   │   ├── market_snapshot.py
│   │   │   ├── instrument_profile.py
│   │   │   └── token_usage.py
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   │   ├── auth.py
│   │   │   ├── market.py
│   │   │   ├── portfolio.py
│   │   │   └── report.py
│   │   └── services/          # Web-specific business logic
│   │       ├── constants.py   # Subset of tuning params for web
│   │       ├── http_client.py # safe_get with retry/backoff
│   │       ├── market_data.py # Market data (web-specific, does NOT import from modules/)
│   │       └── pricing.py     # LLM pricing
│   ├── alembic/               # DB migrations
│   │   └── versions/
│   │       ├── 0001_initial_schema.py
│   │       └── 0002_add_token_usage.py
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # BrowserRouter, ProtectedRoute, routes
│   │   ├── main.tsx           # React entry
│   │   ├── index.css          # Tailwind + Catppuccin Mocha CSS vars
│   │   ├── config.ts          # Runtime config (API base URL etc.)
│   │   ├── api/               # Axios HTTP layer
│   │   │   ├── client.ts      # Axios instance with JWT interceptor
│   │   │   ├── market.ts
│   │   │   ├── portfolio.ts
│   │   │   ├── reports.ts
│   │   │   ├── chat.ts
│   │   │   ├── calendar.ts
│   │   │   └── stats.ts
│   │   ├── stores/
│   │   │   ├── authStore.ts   # Zustand — auth state, JWT
│   │   │   └── appStore.ts    # Zustand — global app state (status messages)
│   │   ├── hooks/
│   │   │   └── useChatStorage.ts
│   │   ├── components/
│   │   │   ├── Layout.tsx     # Navbar + Outlet
│   │   │   ├── InstrumentCard.tsx
│   │   │   ├── InstrumentSearch.tsx
│   │   │   ├── InstrumentProfilePanel.tsx
│   │   │   └── PriceChart.tsx # Lightweight Charts (TradingView)
│   │   └── pages/
│   │       ├── Login.tsx
│   │       ├── Dashboard.tsx  # Main view: instruments + analysis
│   │       ├── Portfolio.tsx
│   │       ├── Calendar.tsx   # Economic calendar
│   │       ├── Charts.tsx     # TradingView charts
│   │       ├── History.tsx    # Report history
│   │       ├── Settings.tsx
│   │       ├── Chat.tsx       # (exists, NOT in App routes yet)
│   │       └── Reports.tsx    # (exists, NOT in App routes yet)
│   ├── package.json
│   ├── vite.config.ts
│   └── index.html
│
├── modules/                   # Desktop business logic (reused by backend via sys.path)
│   ├── ai_engine.py           # AI provider dispatch (Anthropic / OpenAI / OpenRouter)
│   ├── market_data.py         # yfinance / CoinGecko / Stooq
│   ├── database.py            # SQLite CRUD (desktop only)
│   ├── charts.py              # Matplotlib/Tkinter charts (desktop only)
│   ├── scraper.py             # Web scraper with SSRF protection
│   ├── http_client.py         # Shared HTTP session, retry, backoff
│   ├── url_validator.py       # SSRF protection
│   ├── calendar_data.py       # Economic calendar (ForexFactory)
│   ├── news_store.py          # Newsdata.io fetching, dedup
│   ├── news_classifier.py     # Region/topic classification (regex)
│   ├── news_of_day.py         # News scoring engine
│   ├── macro_trend.py         # Macro-trend orchestrator
│   ├── trend_narrative.py     # Trend aggregation & comparison
│   ├── openai_pricing.py      # LLM cost calculation
│   ├── ui_helpers.py          # Tkinter markdown renderer (desktop only)
│   └── exceptions.py          # Custom exceptions
│
├── main.py                    # Legacy Tkinter app (~4550 LOC)
├── config.py                  # Desktop config load/save, env overrides
├── constants.py               # 73 centralized tuning parameters
│
├── data/                      # Desktop runtime data (not versioned)
│   ├── config.json
│   ├── advisor.db
│   └── llm_pricing_cache.json
│
└── tests/                     # Desktop module tests (13 files, 242+ cases)
```

---

## Tech Stack

### Backend
- **FastAPI** — async REST API
- **SQLAlchemy** (async) + **asyncpg** — PostgreSQL ORM
- **Alembic** — database migrations (auto-run on startup)
- **python-jose** + **bcrypt** — JWT auth
- **Pydantic** + **pydantic-settings** — validation, env config
- Desktop `modules/` reused via `sys.path` (project root added in `backend/app/main.py`)

### Frontend
- **React 19** + **TypeScript** + **Vite 7**
- **Tailwind CSS 4** — styling
- **Zustand** — state management
- **Axios** — HTTP client with JWT interceptor
- **React Router 7** — client routing
- **Lightweight Charts** — TradingView chart library
- **react-markdown** — markdown rendering

### Infrastructure
- **Docker Compose** — PostgreSQL 16 + FastAPI (uvicorn) + Nginx
- **Nginx** — reverse proxy + static file serving

---

## Frontend Routes

| Path | Page | Description |
|------|------|-------------|
| `/login` | Login | Auth (unprotected) |
| `/` | Dashboard | Instruments grid + analysis |
| `/portfolio` | Portfolio | Portfolio positions |
| `/calendar` | Calendar | Economic calendar |
| `/charts` | Charts | TradingView charts |
| `/history` | History | Report history |
| `/settings` | Settings | User config |

**Not yet routed:** Chat.tsx, Reports.tsx (pages exist in `src/pages/` but not in App.tsx routes).

---

## API Endpoints

All registered at `/api` prefix. Auth required unless noted.

| Method | Path | Router | Description |
|--------|------|--------|-------------|
| POST | `/api/auth/register` | auth | User registration |
| POST | `/api/auth/login` | auth | Login (returns JWT) |
| POST | `/api/auth/refresh` | auth | Refresh access token |
| GET | `/api/auth/me` | auth | Current user info |
| GET | `/api/market/instruments` | market | All instrument prices |
| POST | `/api/market/sparkline` | market | Sparkline data for symbol |
| GET | `/api/reports` | reports | List reports |
| GET | `/api/reports/{id}` | reports | Report detail |
| POST | `/api/reports/run` | reports | Start AI analysis |
| DELETE | `/api/reports/{id}` | reports | Delete report |
| GET | `/api/portfolio` | portfolio | List positions |
| POST | `/api/portfolio` | portfolio | Add position |
| DELETE | `/api/portfolio/{id}` | portfolio | Delete position |
| POST | `/api/chat` | chat | Chat with AI |
| GET | `/api/settings` | settings | Get user config |
| PUT | `/api/settings` | settings | Update user config |
| GET | `/api/calendar/events` | calendar | Economic calendar events |
| GET | `/api/stats/*` | stats | Token usage statistics |
| GET | `/api/news/*` | news | News feed |
| GET | `/api/health` | (inline) | Health check (no auth) |

---

## Architecture & Data Flow

### Web Application
```
Browser (React)
    │
    ├── Axios + JWT ──→ FastAPI (/api/*)
    │                     ├── backend/app/services/  (web-specific: market_data, http_client)
    │                     ├── modules/               (reused: ai_engine, scraper, news, etc.)
    │                     └── PostgreSQL (via async SQLAlchemy)
    │
    └── Vite dev server (localhost:5173) ──→ proxy to backend (localhost:8000)
```

### Desktop Application (legacy)
```
Tkinter GUI (main.py)
    ├── modules/market_data.py ──→ yfinance / CoinGecko / Stooq
    ├── modules/macro_trend.py ──→ news pipeline
    ├── modules/scraper.py ──→ web scraping
    └── modules/ai_engine.py ──→ AI providers
            └── modules/database.py ──→ SQLite
```

---

## Web Services Layer (`backend/app/services/`)

The web backend has its own copies of some modules, independent from desktop `modules/`:

| Service | Source | Notes |
|---------|--------|-------|
| `services/market_data.py` | Web-specific | Imports from `.http_client`, `.constants` (NOT from `modules/`) |
| `services/http_client.py` | Web-specific | safe_get with retry/backoff |
| `services/constants.py` | Web-specific | Subset of tuning params |
| `services/pricing.py` | Web-specific | LLM pricing |

Other backend routes still import from desktop `modules/` (e.g., `ai_engine`, `calendar_data`, `scraper`).

---

## Database

### Web: PostgreSQL (via async SQLAlchemy + Alembic)

Models in `backend/app/models/`:

| Model | Table |
|-------|-------|
| User | users |
| Report | reports |
| Portfolio | portfolio |
| Alert | alerts |
| MarketSnapshot | market_snapshots |
| InstrumentProfile | instrument_profiles |
| TokenUsage | token_usage |

Migrations: `backend/alembic/versions/` (2 migrations: initial schema + token usage).

### Desktop: SQLite (`data/advisor.db`)

Tables: reports, market_snapshots, alerts, portfolio, instrument_profiles, news_items.

---

## Configuration

### Web Backend (`backend/app/core/config.py`)

Pydantic Settings, loaded from `.env` file:

| Setting | Default | Description |
|---------|---------|-------------|
| `SECRET_KEY` | (change me) | JWT signing key |
| `DEBUG` | false | Debug mode |
| `DATABASE_URL` | `postgresql+asyncpg://advisor:advisor@localhost:5432/advisor` | DB connection |
| `CORS_ORIGINS` | localhost:5173, localhost:3000 | Allowed origins |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 1440 (24h) | JWT access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 30 | Refresh token TTL |
| `ANTHROPIC_API_KEY` | "" | Server-wide AI key fallback |
| `OPENAI_API_KEY` | "" | Server-wide AI key fallback |
| `OPENROUTER_API_KEY` | "" | Server-wide AI key fallback |
| `NEWSDATA_KEY` | "" | News API key |

### Desktop (`data/config.json`)

Auto-created on first run. Key fields: `api_keys.*`, `ai_provider`, `ai_model`, `chat_provider`, `chat_model`, `instruments`, `sources`, `trusted_domains`, `prompt`, `chat_prompt`, `schedule.*`.

Env var overrides: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `NEWSDATA_KEY`.

---

## AI Provider Logic (`modules/ai_engine.py`)

1. **`_call_provider(provider, ...)`** — unified dispatch
   - `"anthropic"` → `anthropic.Anthropic` client
   - `"openai"` → `openai.OpenAI` client
   - `"openrouter"` → `openai.OpenAI` with `base_url="https://openrouter.ai/api/v1"`
2. Token kwarg auto-handling (max_tokens vs max_completion_tokens)
3. **`run_analysis()`** — market data + news + scraped text → AI report
4. **`run_chat()`** — multi-turn chat with conversation history
5. Cost tracking via `openai_pricing.py`

### Available AI Models

- **Anthropic:** `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`
- **OpenAI:** `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `o3`, `o3-mini`, `o4-mini`, `o1`, `o1-preview`, `o1-mini`
- **OpenRouter:** Any model via `provider/model` format

---

## Market Data Sources

| Source | Function | Data |
|--------|----------|------|
| yfinance | `get_yfinance_data()` | Stocks, indices, forex, commodities |
| CoinGecko | `get_coingecko_data()` | Crypto (rate-limited: 2.5s, 10min cache) |
| Stooq | `get_stooq_data()` | Polish instruments (CSV API) |

---

## Visual Theme

**Catppuccin Mocha** — CSS custom properties in `frontend/src/index.css`:

```css
--bg: #1e1e2e;      --bg2: #181825;
--fg: #cdd6f4;       --accent: #89b4fa;
--green: #a6e3a1;    --red: #f38ba8;
--yellow: #f9e2af;   --gray: #313244;
--surface: #1e1e2e;  --overlay: #6c7086;
```

Fonts: Plus Jakarta Sans (UI), Newsreader (chat replies).

---

## Security

### Auth (web)
- JWT access tokens (24h) + refresh tokens (30d)
- bcrypt password hashing
- Protected routes via `get_current_user` dependency

### SSRF Protection (`modules/url_validator.py`)
- Scheme, IP, hostname, DNS checks before scraper HTTP requests
- Domain allowlist support

### HTTP Client (`modules/http_client.py`)
- Retry with exponential backoff (429/5xx)
- URL masking in logs (apiKey, token, secret, password params)

### API Keys
- Env vars override config file (desktop)
- Keys never logged or committed
- `mask_key()` for display

---

## Coding Conventions

- **UI and prompt language:** Polish
- **Code comments:** mixed Polish/English — preserve existing style per file
- **Error pattern:** `{"error": "..."}` dicts on failure (desktop modules)
- **Constants:** centralized in `constants.py` (desktop) and `services/constants.py` (web)
- **Style:** straightforward, minimal abstraction
- **Web backend:** async FastAPI, Pydantic schemas, SQLAlchemy models
- **Web frontend:** functional React components, Zustand stores, Tailwind utility classes

---

## Common Development Tasks

### Add a New Backend Endpoint
1. Create/update router in `backend/app/api/`
2. Add Pydantic schemas in `backend/app/schemas/`
3. Register router in `backend/app/main.py` if new file
4. Add Alembic migration if DB schema changes

### Add a New Frontend Page
1. Create page component in `frontend/src/pages/`
2. Add route in `frontend/src/App.tsx`
3. Add nav item in `frontend/src/components/Layout.tsx` `navItems` array
4. Add API functions in `frontend/src/api/` if needed

### Add a New Alembic Migration
```bash
cd backend
alembic revision --autogenerate -m "description"
```
Migrations auto-run on backend startup.

### Add a New Market Data Source
1. Add `get_XYZ_data()` in `backend/app/services/market_data.py` (web) or `modules/market_data.py` (desktop)
2. Handle new `"source"` in `get_all_instruments()`

### Add a New AI Provider
1. Add branch in `_call_provider()` in `modules/ai_engine.py`
2. Add to `get_available_models()` and `_PROVIDER_DEFAULTS`
3. Add env variable mapping

---

## Known Issues / TODO

1. **Chat and Reports pages not routed** — `Chat.tsx` and `Reports.tsx` exist but are not in `App.tsx` routes
2. **No HTTPS yet** — currently HTTP only; need Certbot/Let's Encrypt for SSL
3. **Desktop `main.py` is 4550+ LOC** — monolithic Tkinter class, preserved for reference
4. **Synchronous AI calls** — `run_analysis()` / `run_chat()` block; no timeout to API clients
5. **SSRF TOCTOU risk** — DNS validated at check time, HTTP request happens later
6. **No SSRF on non-scraper HTTP** — CoinGecko/Stooq calls don't go through URL validator
7. **Mixed module usage** — some backend routes use desktop `modules/` directly, others use `services/`
8. **No WebSocket yet** — planned for real-time price updates, not implemented
9. **Web pricing scrape brittle** — `openai_pricing.py` SPA scrape always fails, hardcoded fallback works
10. **No web tests yet** — only desktop module tests exist
11. **PostgreSQL password** — default `advisor:advisor` in docker-compose; change for production

---

## What to Be Careful About

1. **`services/` vs `modules/`** — web backend has its own `services/market_data.py`. Don't confuse with desktop `modules/market_data.py`. Keep them independent.
2. **sys.path manipulation** — `backend/app/main.py` adds project root to sys.path so desktop `modules/` are importable. Changing project structure may break this.
3. **API key safety** — never log, print, or commit API keys. Use env vars.
4. **Alembic migrations** — auto-run on startup. Test migrations locally before deploying.
5. **Config schema** — adding desktop config fields requires backward-compatible defaults in `load_config()`.
6. **Prompt changes** — system prompts in `config.json` may be user-customized. Don't overwrite.
7. **Thread safety** — desktop modules use threading.Lock/RLock for shared state.
8. **Desktop test suite** — run `python -m unittest discover tests/ -v` before pushing changes to `modules/`.
