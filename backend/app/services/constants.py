"""Stałe konfiguracyjne dla web backendu InvestmentAdvisor.

Kopia z głównego constants.py — wersja niezależna od aplikacji desktopowej.
"""

from zoneinfo import ZoneInfo

# ── Timezone ─────────────────────────────────────────────────────
APP_TIMEZONE_NAME = "Europe/Warsaw"
APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)

# ── Network / HTTP ────────────────────────────────────────────────
HTTP_CONNECT_TIMEOUT = 8
HTTP_READ_TIMEOUT = 15
HTTP_DEFAULT_TIMEOUT = (HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT)
HTTP_MAX_RETRIES = 2
HTTP_BACKOFF_FACTOR = 1.0
HTTP_RETRY_STATUS_CODES = [429, 500, 502, 503, 504]
HTTP_AUTH_ERROR_CODES = (401, 403)

# ── URL masking ───────────────────────────────────────────────────
URL_MASK_PREFIX_LENGTH = 4
URL_MASK_MIN_LENGTH = 6

# ── FX / Market data ─────────────────────────────────────────────
FX_CACHE_TTL = 600                # 10 min
YFINANCE_HISTORY_PERIOD = "5d"
PRICE_ROUND_DECIMALS = 4
CHANGE_PCT_ROUND_DECIMALS = 2

# ── News ──────────────────────────────────────────────────────────
NEWS_DEFAULT_PAGE_SIZE = 50
