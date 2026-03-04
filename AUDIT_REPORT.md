# InvestmentAdvisor — Deep Audit Report

**Date:** 2026-03-04
**Scope:** All source files, tests, configuration, and dependencies
**Method:** File-by-file static analysis, no code modifications

---

## 1. Executive Summary

### Top 5 Highest-Impact Issues

| # | Issue | Category | Impact |
|---|-------|----------|--------|
| 1 | **Duplicate news classification runs 5x** on the same data in `macro_trend.py` | Performance / AI Costs | Eliminates ~80% of classification overhead per analysis cycle |
| 2 | **No timeout on AI provider API calls** — a stalled Anthropic/OpenAI call blocks the worker thread indefinitely | Stability | Prevents indefinite hangs; unblocks stuck analysis |
| 3 | **Chat history grows unbounded** — full conversation sent with every message, no token limit | AI Costs | Can save 50-80% of chat token costs on long conversations |
| 4 | **`main.py` is 4300+ LOC in a single class** — high merge conflict risk, hard to navigate | Code Quality | Reduces cognitive load, enables parallel development |
| 5 | **SSRF protection not applied to market data URLs** — user-provided symbols injected into CoinGecko/Stooq URLs without validation | Security | Closes server-side request forgery vector via crafted instrument symbols |

### Estimated Overall Impact (if all HIGH+ issues resolved)

- **~60% reduction in unnecessary token spending** (duplicate classification, unbounded chat history, missing token limits)
- **3 crash/hang paths eliminated** (AI timeout, matplotlib thread safety, unhandled empty responses)
- **2 security vectors closed** (symbol injection into URLs, hardcoded plaintext password)
- **~40% improvement in analysis cycle time** (skip redundant classification, cache news between runs)

---

## 2. Full Findings by Category

---

### 2.1 PERFORMANCE

---

#### P1: Duplicate news classification in macro_trend.py

```
[PRIORITY: HIGH]
Problem: classify_articles() is called 5 times — once on raw fetched articles, then again
         on each of 4 DB query results (24h, 7d, 30d, 90d). The DB rows already have
         region/topic from the first classification + storage, making re-classification redundant.
Location: modules/macro_trend.py lines 55-75 (build_macro_payload)
Fix: Remove the 4 redundant classify_articles() calls on DB query results. Only classify once
     on raw_articles before storing. Ensure store_news() persists region/topic (it already does).
Impact: Eliminates ~80% of classification CPU per analysis cycle (~17 regex * articles * 4 passes).
```

---

#### P2: No caching of market data between analysis and chart rendering

```
[PRIORITY: MEDIUM]
Problem: When a user runs analysis and then opens a chart for the same instrument, data is
         fetched again from yfinance/CoinGecko. The analysis already fetched all instrument data
         via get_all_instruments().
Location: modules/charts.py:fetch_chart_data() (line 90), main.py:_draw_chart()
Fix: Pass already-fetched data to chart rendering when available, or add a short TTL cache
     (e.g., 5 min) to fetch_chart_data().
Impact: Saves 1 API call per chart open after analysis. Reduces chart load time by ~1-3s.
```

---

#### P3: Newsdata.io windows fetched sequentially

```
[PRIORITY: MEDIUM]
Problem: fetch_all_windows() in news_store.py iterates 5 time windows (24h, 72h, 7d, 30d, 90d)
         sequentially. Each window makes an HTTP request to Newsdata.io.
Location: modules/news_store.py:fetch_all_windows() (line 221)
Fix: Use ThreadPoolExecutor to fetch windows in parallel (with fail-fast on auth error via
     shared flag). Respect Newsdata.io rate limits.
Impact: Reduces news fetching time from ~5 sequential requests to ~1-2 parallel batches.
```

---

#### P4: Matplotlib figures not always closed after chart replacement

```
[PRIORITY: MEDIUM]
Problem: When user changes chart period/symbol, old figures are closed via plt.close(fig),
         but if create_price_chart() raises an exception after creating the figure but before
         returning, the figure leaks. Also, _build_chart_toolbar() creates a hidden
         NavigationToolbar2Tk that is never destroyed.
Location: main.py:_draw_chart() (lines 1944-1981), modules/charts.py:_build_chart_toolbar() (line 372)
Fix: Use try/finally to ensure plt.close(fig) on exception. Track and destroy hidden toolbars.
Impact: Prevents gradual memory growth in long sessions (~2-5 MB per leaked figure).
```

---

#### P5: CoinGecko rate limiter uses time.sleep() blocking the calling thread

```
[PRIORITY: LOW]
Problem: _cg_rate_wait() in market_data.py calls time.sleep() which blocks the calling thread.
         When called from the main analysis thread, this adds up to 2.5s of dead time per
         CoinGecko request.
Location: modules/market_data.py:_cg_rate_wait() (lines 33-41)
Fix: The batch optimization in get_all_instruments() already minimizes CoinGecko calls.
     For chart data, consider async fetching or accept the delay.
Impact: Minor — batch optimization already mitigates this for the main analysis flow.
```

---

#### P6: _EVENT_SIGNIFICANCE dict lookup is O(n) per event

```
[PRIORITY: LOW]
Problem: get_event_significance() in calendar_data.py iterates 170+ keyword entries for each
         calendar event, checking substring inclusion.
Location: modules/calendar_data.py:get_event_significance() (line 139)
Fix: Precompile into a single regex pattern with named groups, or use a trie for O(k) lookup.
Impact: Negligible for typical calendar sizes (50-100 events), but could matter for bulk processing.
```

---

### 2.2 AI PROVIDER COSTS

---

#### C1: Chat history grows without token limit

```
[PRIORITY: CRITICAL]
Problem: _chat_history in main.py accumulates all messages and sends the entire history with
         every run_chat() call. There is no truncation, summarization, or sliding window.
         A 20-message conversation can easily exceed 10k tokens of context per message.
Location: main.py:_send_chat_message() / _send_chat_message_from(), modules/ai_engine.py:run_chat()
Fix: Implement a sliding window (keep last N messages) or token-budget approach. Summarize
     older messages before they fall off the window. Set max_tokens on chat responses.
Impact: Can save 50-80% of chat token costs for conversations >10 messages. Prevents hitting
        context window limits.
```

---

#### C2: Analysis prompt includes full scraped text without truncation control

```
[PRIORITY: HIGH]
Problem: scrape_all() returns up to 2000 chars per site. With 50+ configured sources, the
         scraped text can be 100k+ chars (~25k tokens). This entire block is sent to the AI.
Location: main.py:_run_analysis() line 3540-3543, modules/ai_engine.py:_build_macro_prompt()
Fix: Add a total scraped text budget (e.g., 8000 chars / ~2k tokens). Prioritize sources by
     relevance or truncate proportionally.
Impact: Could save $0.01-0.10 per analysis call depending on model. Prevents context overflow.
```

---

#### C3: No response token limit differentiation by task type

```
[PRIORITY: MEDIUM]
Problem: AI_MAX_TOKENS (8192) is used for analysis, chat, profiles, and calendar event analysis
         alike. Profiles and event analyses need far fewer tokens (~500-1000).
Location: modules/ai_engine.py:generate_instrument_profile() line 218,
          generate_calendar_event_analysis() line 255
Fix: Use task-specific max_tokens: analysis=8192, chat=2048 (already done via AI_CHAT_MAX_TOKENS),
     profiles=1024, calendar events=1024.
Impact: Reduces output token costs for profile/event calls by ~75%. Faster responses.
```

---

#### C4: No caching of AI-generated instrument profiles

```
[PRIORITY: MEDIUM]
Problem: Instrument profiles are generated via AI and saved to SQLite (instrument_profiles table).
         However, the code in main.py always checks DB first (get_instrument_profile), so this
         is partially handled. The issue is that profiles have no expiry — stale profiles persist
         indefinitely, and there's no mechanism to regenerate them periodically.
Location: modules/database.py:get_instrument_profile(), main.py:_open_instrument_profile()
Fix: Add a TTL column to instrument_profiles (e.g., 30 days). Regenerate when stale.
Impact: Low cost impact but keeps profiles accurate as market conditions change.
```

---

#### C5: Chart chat sends full chat history on every message

```
[PRIORITY: MEDIUM]
Problem: _chart_chat_history in main.py is separate from main chat history but has the same
         unbounded growth problem. Each chart question sends all prior chart messages.
Location: main.py:_chart_chat_history (line 127), chart chat send logic
Fix: Apply same sliding window as main chat (see C1).
Impact: Same as C1 for users who use chart chat extensively.
```

---

### 2.3 STABILITY & RELIABILITY

---

#### S1: No timeout on AI provider API calls

```
[PRIORITY: CRITICAL]
Problem: _call_provider() in ai_engine.py calls anthropic.messages.create() and
         openai.chat.completions.create() without a timeout parameter. If the API stalls
         (network issue, provider outage), the worker thread blocks indefinitely. The UI
         shows "Analizuję..." forever with no way to cancel.
Location: modules/ai_engine.py:_call_provider() lines 56-78
Fix: Pass timeout=120 (or configurable) to both Anthropic and OpenAI client calls.
     Add a cancellation mechanism (e.g., threading.Event checked between retries).
Impact: Eliminates indefinite hang path. Users can retry after timeout instead of force-quitting.
```

---

#### S2: news_store.py runs init_news_table() on import

```
[PRIORITY: HIGH]
Problem: Importing news_store.py immediately calls init_news_table() (line 321), which creates
         the data/ directory and SQLite database. This is a side effect of module import that
         runs during test collection and makes the module harder to test in isolation.
Location: modules/news_store.py line 321
Fix: Remove the import-time call. Call init_news_table() explicitly during app startup
     (alongside database.init_db()).
Impact: Cleaner test isolation, no surprise filesystem side effects on import.
```

---

#### S3: Config load has no error handling for malformed JSON

```
[PRIORITY: HIGH]
Problem: load_config() in config.py calls json.load(f) without try/except. If config.json is
         corrupted (truncated write, disk error), the app crashes on startup with an unhandled
         JSONDecodeError.
Location: config.py:load_config()
Fix: Wrap json.load in try/except JSONDecodeError. On failure, back up the corrupt file and
     create fresh defaults. Log a warning.
Impact: Prevents crash-on-startup from corrupt config. Preserves user data via backup.
```

---

#### S4: schedule library runner has no exception handling

```
[PRIORITY: HIGH]
Problem: The scheduler runner thread in main.py (lines 3971-3974) calls
         schedule.run_pending() in a loop. If the scheduled job (_run_analysis_thread) raises
         an unhandled exception, the schedule library catches it but logs to stderr. However,
         if schedule.run_pending() itself fails, the runner thread dies silently.
Location: main.py:_start_scheduler() lines 3965-3976
Fix: Wrap schedule.run_pending() in try/except with logging. Restart the runner on failure.
Impact: Prevents silent scheduler death. Ensures scheduled analyses continue running.
```

---

#### S5: CoinGecko batch failure silently marks all coins as error

```
[PRIORITY: MEDIUM]
Problem: In get_all_instruments(), if the batch CoinGecko price fetch fails, all individual
         CoinGecko instruments fall through to individual fetches. But if the individual fetches
         also fail (e.g., rate limit), each coin gets {"error": "..."} with no retry.
Location: modules/market_data.py:get_all_instruments() lines 276-300
Fix: Add a single retry for the batch call with a 3s delay. If batch succeeds partially,
     only retry failed coins individually.
Impact: Reduces "N/A" price displays when CoinGecko has transient issues.
```

---

#### S6: Matplotlib not thread-safe but chart data fetched inside create_price_chart

```
[PRIORITY: MEDIUM]
Problem: create_price_chart() in charts.py both fetches data (blocking I/O via yfinance/CoinGecko)
         AND creates matplotlib figures. It's called from the main thread, so the I/O blocks
         the UI. Moving the fetch to a worker thread would be ideal, but matplotlib figure
         creation must stay on the main thread.
Location: modules/charts.py:create_price_chart() lines 160-362
Fix: Split into two phases: (1) fetch data in background thread, (2) create chart on main
     thread via self.after(). This is partially done for the dashboard but not for the charts tab.
Impact: Eliminates UI freeze during chart loading (1-5s depending on source).
```

---

#### S7: datetime.utcnow() is deprecated

```
[PRIORITY: LOW]
Problem: Multiple modules use datetime.utcnow() which is deprecated in Python 3.12+.
         Returns naive datetime, can cause timezone confusion.
Location: modules/news_store.py (lines 139, 243, 278, 296, 312),
          modules/news_of_day.py (line 101)
Fix: Replace with datetime.now(timezone.utc) for timezone-aware UTC datetimes.
Impact: Future-proofs against Python deprecation warnings. Prevents subtle timezone bugs.
```

---

#### S8: Scraper has no retry logic

```
[PRIORITY: LOW]
Problem: scraper.py creates its HTTP session with max_retries=0 (line 37). A transient
         connection error on any URL means that source is lost entirely for that analysis.
Location: modules/scraper.py:_build_scraper_session() line 37
Fix: Set max_retries=1 with a short backoff. Since scraping runs in parallel with a per-URL
     timeout, a single retry adds minimal latency.
Impact: Recovers from ~10-20% of transient failures without meaningful delay.
```

---

### 2.4 SECURITY

---

#### X1: User-provided symbols injected into URLs without validation

```
[PRIORITY: HIGH]
Problem: In market_data.py, instrument symbols from config are interpolated directly into
         CoinGecko and Stooq URLs (f-strings). A crafted symbol like
         "bitcoin/market_chart?vs_currency=usd&days=1#" could manipulate the URL path.
         The SSRF protection in url_validator.py only covers the scraper, not market data calls.
Location: modules/market_data.py lines 105, 183, 324 (charts.py line 59)
Fix: Validate symbols against a regex (alphanumeric + limited special chars). URL-encode
     symbol values. Consider applying url_validator to all external HTTP calls.
Impact: Closes URL injection vector via crafted instrument configs.
```

---

#### X2: Hardcoded plaintext password for settings protection

```
[PRIORITY: HIGH]
Problem: _SETTINGS_PASSWORD = "666" is hardcoded in main.py (line 250). This "protects" the
         prompts/settings tab. The password is trivially discoverable in source code.
Location: main.py line 250
Fix: Either hash the password (store hash in config) or remove the password protection entirely
     (it provides false sense of security for a local desktop app). If needed, use OS-level
     keychain integration.
Impact: Eliminates false security. Users won't rely on a trivially bypassed mechanism.
```

---

#### X3: Newsdata.io API key visible in URL query parameters

```
[PRIORITY: MEDIUM]
Problem: In news_store.py and market_data.py, the Newsdata.io API key is passed as a query
         parameter (?apikey=...). While http_client.py masks this in error logs, the key is
         still visible in HTTP request URLs, proxy logs, and potentially browser history.
Location: modules/news_store.py:_newsdata_request() line 171,
          modules/market_data.py:get_news() line 363
Fix: This is a Newsdata.io API design limitation (they require key in URL). Ensure all logging
     goes through http_client's masking. Add a warning in documentation.
Impact: Acknowledged limitation. Masking in logs is already in place.
```

---

#### X4: Markdown links opened without user confirmation

```
[PRIORITY: MEDIUM]
Problem: ui_helpers.py:_insert_inline() binds markdown links to webbrowser.open(url)
         without confirmation. If AI generates a malicious link in its response, clicking it
         would navigate to an untrusted URL.
Location: modules/ui_helpers.py line 168
Fix: Show a confirmation dialog ("Open URL: {url}?") before calling webbrowser.open().
Impact: Prevents drive-by navigation to malicious URLs generated by AI or scraped content.
```

---

#### X5: No input sanitization on ticker symbols in UI

```
[PRIORITY: LOW]
Problem: Users can add arbitrary strings as instrument symbols via the settings UI. These
         strings are used in API URLs, database queries, and file paths without validation.
Location: main.py settings tab (instrument list editing)
Fix: Validate symbols against a whitelist regex (e.g., ^[A-Za-z0-9._^=-]{1,20}$) when
     saving settings.
Impact: Defense-in-depth. Prevents malformed symbols from causing unexpected behavior.
```

---

#### X6: Crontab entries built without shell escaping

```
[PRIORITY: LOW]
Problem: _update_cron_schedule() in main.py builds crontab command strings by interpolating
         Python path and script path. If these paths contain spaces or special characters,
         the cron entry may break or execute unintended commands.
Location: main.py:_update_cron_schedule() lines 2479-2481
Fix: Use shlex.quote() on path components when building crontab entries.
Impact: Prevents cron entry breakage on systems with spaces in paths.
```

---

### 2.5 CODE QUALITY & MAINTAINABILITY

---

#### Q1: main.py is 4300+ lines in a single class

```
[PRIORITY: HIGH]
Problem: The InvestmentAdvisor class contains 150+ methods handling UI building, event handling,
         analysis orchestration, PDF export, scheduling, chart management, portfolio management,
         alerts, settings, and more. This makes the file extremely hard to navigate, review,
         and modify without merge conflicts.
Location: main.py (entire file)
Fix: Extract logical groups into separate modules:
     - ui/dashboard.py, ui/charts_tab.py, ui/portfolio_tab.py, ui/settings_tab.py
     - pdf_export.py
     - scheduler.py
     Keep main.py as the entry point with the Notebook skeleton.
Impact: Dramatically improves maintainability and enables parallel development.
```

---

#### Q2: Duplicate HTTP session/header definitions

```
[PRIORITY: MEDIUM]
Problem: Both http_client.py and scraper.py define their own User-Agent headers, session
         builders, and thread-safe singleton patterns. The code is nearly identical.
Location: modules/http_client.py lines 29-83, modules/scraper.py lines 22-53
Fix: Have scraper.py use http_client's session (with scraper-specific config like max_redirects).
     Remove duplicate header definitions.
Impact: Reduces maintenance burden. Single place to update HTTP behavior.
```

---

#### Q3: Theme colors defined in 3 places

```
[PRIORITY: MEDIUM]
Problem: Catppuccin Mocha colors are defined independently in main.py (lines 41-48),
         charts.py (COLORS dict, line 23), and ui_helpers.py (lines 17-24). Changes to the
         theme require updating all three.
Location: main.py, modules/charts.py, modules/ui_helpers.py
Fix: Move all color definitions to constants.py and import everywhere.
Impact: Single source of truth for theme. Easier to add theme switching later.
```

---

#### Q4: Duplicate error handling pattern in ai_engine.py

```
[PRIORITY: LOW]
Problem: _run_provider() and run_chat() catch identical exception tuples
         (anthropic.APIError, openai.OpenAIError, KeyError, ValueError, ConnectionError,
         TimeoutError) with nearly identical handling.
Location: modules/ai_engine.py lines 99-102, 194-197
Fix: Extract common error handling into a decorator or helper function.
Impact: Reduces code duplication, ensures consistent error handling.
```

---

#### Q5: sys.path manipulation in multiple modules

```
[PRIORITY: LOW]
Problem: Multiple modules (charts.py, news_of_day.py, news_store.py, macro_trend.py,
         trend_narrative.py, openai_pricing.py, ui_helpers.py) use
         sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
         to import from constants.py.
Location: 7 modules under modules/
Fix: Use relative imports (from ..constants import ...) or restructure as a proper Python
     package with __init__.py at root.
Impact: Cleaner imports, prevents path pollution, follows Python packaging conventions.
```

---

#### Q6: Custom exceptions defined but rarely used

```
[PRIORITY: LOW]
Problem: modules/exceptions.py defines DataFetchError, AIProviderError, and ScraperError,
         but most code catches broad Exception or specific library exceptions. The custom
         exceptions are mostly unused.
Location: modules/exceptions.py, modules/ai_engine.py, modules/market_data.py, modules/scraper.py
Fix: Gradually adopt custom exceptions in modules. Raise DataFetchError from market_data
     failures, AIProviderError from ai_engine failures, ScraperError from scraper failures.
     This enables more targeted error handling in main.py.
Impact: Better error categorization. Main.py can handle different failure types differently.
```

---

#### Q7: Test coverage gaps for critical modules

```
[PRIORITY: MEDIUM]
Problem: Several modules have zero or minimal test coverage:
         - config.py — no tests (config load, save, env override)
         - scraper.py — no tests (URL fetch, HTML parse, parallel scrape)
         - calendar_data.py — no tests
         - openai_pricing.py — no tests (cost calculation, cache logic)
         - http_client.py — only _mask_url() tested; safe_get() not tested
         - main.py — no tests (UI, but this is expected for Tkinter)
Location: tests/ directory
Fix: Priority additions:
     1. test_config.py — config load/save, env overrides, malformed file handling
     2. test_scraper.py — mocked HTTP, HTML parsing, parallel execution
     3. test_openai_pricing.py — cost calculation, cache TTL, prefix matching
     4. Expand test_http_client.py — safe_get retry, timeout, size limit
Impact: Catches regressions in config, scraping, and pricing — all critical paths.
```

---

## 3. Quick Wins (fixes under 30 minutes each)

| # | Fix | File | Time Est. |
|---|-----|------|-----------|
| 1 | Remove 4 redundant `classify_articles()` calls in `build_macro_payload()` | `macro_trend.py` | 5 min |
| 2 | Add `timeout=120` parameter to Anthropic and OpenAI API calls | `ai_engine.py` | 10 min |
| 3 | Add `try/except JSONDecodeError` in `load_config()` with backup + defaults | `config.py` | 15 min |
| 4 | Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` everywhere | `news_store.py`, `news_of_day.py` | 10 min |
| 5 | Add `try/except` around `schedule.run_pending()` in scheduler runner | `main.py` | 5 min |
| 6 | Move color constants to `constants.py`, import everywhere | `constants.py`, 3 files | 20 min |
| 7 | Add symbol validation regex in `market_data.py` before URL construction | `market_data.py` | 15 min |
| 8 | Add sliding window (last 20 messages) to chat history before sending | `main.py` | 15 min |
| 9 | Set `max_retries=1` in scraper session builder | `scraper.py` | 2 min |
| 10 | Remove `init_news_table()` call from module-level in `news_store.py` | `news_store.py`, `main.py` | 5 min |

---

## 4. Estimated Overall Impact if All HIGH+ Issues Are Resolved

### Token Cost Reduction
- **~60% reduction in unnecessary token spending** — from eliminating unbounded chat history (C1/C5), reducing scraped text payload (C2), and using task-specific max_tokens (C3)
- At 2 analyses + 10 chat messages per day with gpt-4o: estimated savings of ~$0.50-1.00/day

### Stability Improvement
- **3 potential hang/crash paths eliminated:**
  1. AI provider timeout hang (S1)
  2. Corrupt config.json crash (S3)
  3. Silent scheduler death (S4)
- **2 data loss paths prevented:**
  1. Config corruption recovery (S3)
  2. Graceful degradation on CoinGecko batch failure (S5)

### Performance Improvement
- **~40% faster analysis cycles** — from skipping redundant classification (P1), parallelizing news fetches (P3)
- **Eliminated UI freezes** — from separating chart data fetch from rendering (S6)

### Security Improvement
- **2 attack vectors closed:**
  1. Symbol injection into market data URLs (X1)
  2. Hardcoded password replaced/removed (X2)
- **1 phishing vector mitigated:**
  1. Link click confirmation dialog (X4)

### Maintainability Improvement
- **Splitting main.py** into logical modules reduces average change scope from 4300 LOC to ~500-800 LOC per module
- **Single source of truth** for colors, HTTP config, and error handling
- **Test coverage** expanded from 8/15 modules to 12/15 modules
