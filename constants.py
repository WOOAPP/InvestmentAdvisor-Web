"""Centralized constants for InvestmentAdvisor.

All magic numbers, limits, timeouts, and tunable parameters live here.
Modules import what they need instead of using hardcoded literals.
"""

# ── Network / HTTP ────────────────────────────────────────────────
HTTP_CONNECT_TIMEOUT = 8          # seconds
HTTP_READ_TIMEOUT = 15            # seconds
HTTP_DEFAULT_TIMEOUT = (HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT)
HTTP_MAX_RETRIES = 2
HTTP_BACKOFF_FACTOR = 1.0         # 1 s, 2 s between retries
HTTP_RETRY_STATUS_CODES = [429, 500, 502, 503, 504]
HTTP_AUTH_ERROR_CODES = (401, 403)

# ── Scraper / URL validator ───────────────────────────────────────
SCRAPER_MAX_REDIRECTS = 3
SCRAPER_MAX_URLS_PER_RUN = 20
SCRAPER_MAX_RESPONSE_BYTES = 2 * 1024 * 1024   # 2 MB
SCRAPER_CHUNK_SIZE = 8192
SCRAPER_DEFAULT_MAX_CHARS = 3000
SCRAPER_MAX_CHARS_PER_SITE = 2000
SCRAPER_MIN_LINE_LENGTH = 40      # shorter lines stripped as noise

# ── FX / Market data ─────────────────────────────────────────────
FX_CACHE_TTL = 600                # 10 min
YFINANCE_HISTORY_PERIOD = "5d"
PRICE_ROUND_DECIMALS = 4
CHANGE_PCT_ROUND_DECIMALS = 2

# ── AI engine ─────────────────────────────────────────────────────
AI_MAX_TOKENS_ANALYSIS = 8192
AI_MAX_TOKENS_CHAT = 2048
LEGACY_NEWS_LIMIT = 8             # max news items in legacy prompt
LEGACY_DESCRIPTION_TRUNCATE = 150

# ── Database ──────────────────────────────────────────────────────
DB_DEFAULT_REPORTS_LIMIT = 50
DB_REPORT_PREVIEW_LENGTH = 200
DB_DEFAULT_PRICE_HISTORY_DAYS = 30
DB_PRICE_HISTORY_MULTIPLIER = 10  # rows = days * multiplier

# ── News store ────────────────────────────────────────────────────
NEWS_HASH_LENGTH = 16
NEWS_DESCRIPTION_MAX_LENGTH = 500
NEWS_DEFAULT_PAGE_SIZE = 50
NEWS_CLEANUP_DAYS = 100
NEWS_DEFAULT_LIMIT_BY_WINDOW = 50
NEWS_DEFAULT_LIMIT_SINCE = 100
NEWS_DEFAULT_LIMIT_IN_RANGE = 200

# ── Macro trend / LLM payload ────────────────────────────────────
MACRO_MAX_24H_TO_LLM = 20
MACRO_MAX_LONGER_WINDOW = 50
MACRO_24H_HOURS = 72              # "24h" window actually covers 72 h
MACRO_GEO_ARTICLES_PER_REGION = 5
MACRO_SLIM_DESCRIPTION_TRUNCATE = 120
MACRO_SLIM_TOP_REGIONS = 3
MACRO_SLIM_TOP_TOPICS = 3
MACRO_SLIM_TOP_KEYWORDS = 5
MACRO_DISPLAY_24H_LIMIT = 15
MACRO_DISPLAY_TITLE_TRUNCATE = 100
MACRO_DISPLAY_GEO_TITLES = 3

# ── News of the day — scoring ────────────────────────────────────
NOD_DEFAULT_SOURCE_WEIGHT = 3
NOD_RECENCY_MAX_SCORE = 10.0
NOD_RECENCY_MIN_SCORE = 1.0
NOD_RECENCY_UNKNOWN_SCORE = 2.0
NOD_RECENCY_WINDOW_HOURS = 72.0
NOD_KEYWORD_BASE_BONUS = 3.0
NOD_KEYWORD_MAX_BONUS = 6.0
NOD_SCORE_WEIGHT_SOURCE = 1.5
NOD_SCORE_WEIGHT_RECENCY = 1.0
NOD_SCORE_WEIGHT_KEYWORD = 2.0
NOD_SCORE_WEIGHT_TOPIC = 1.5
NOD_MAX_JUSTIFICATION = 6
NOD_MAX_WATCH_SIGNALS = 5
NOD_SAME_TOPIC_STRONG = 5
NOD_SAME_TOPIC_MODERATE = 3

# ── Trend narrative ───────────────────────────────────────────────
TREND_TOP_KEYWORDS = 10
TREND_TOP_REGIONS = 6
TREND_TOP_TOPICS = 8
TREND_NEW_TOPIC_THRESHOLD = 0.5
TREND_DIFF_KEYWORDS_LIMIT = 5

# ── Charts ────────────────────────────────────────────────────────
CHART_MA_SHORT_PERIOD = 20        # MA20
CHART_MA_LONG_PERIOD = 50         # MA50
CHART_MAX_COMPARE_SYMBOLS = 3
CHART_SPARSE_DATA_THRESHOLD = 10  # add dot markers below this

# ── Pricing cache ─────────────────────────────────────────────────
PRICING_CACHE_TTL = 86400         # 24 h
PRICING_TOKENS_PER_UNIT = 1_000_000

# ── UI / Window ───────────────────────────────────────────────────
UI_MIN_WINDOW_WIDTH = 1024
UI_MIN_WINDOW_HEIGHT = 700
SPINNER_TICK_MS = 100
URL_MASK_PREFIX_LENGTH = 4
URL_MASK_MIN_LENGTH = 6
