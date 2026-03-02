"""LLM API pricing: fetch from OpenAI, cache locally, fallback to hardcoded rates.

Provides ``get_model_cost(model_key, input_tokens, output_tokens)``
returning cost in USD (float) or *None* when the model is unknown.
"""

import json
import logging
import os
import re
import time

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CACHE_FILE = os.path.join(DATA_DIR, "llm_pricing_cache.json")
CACHE_TTL = 86400  # 24 h

PRICING_URL = "https://openai.com/pl-PL/api/pricing/"

# ── Fallback pricing: USD per 1 M tokens, Standard tier ──────────
# Sources (March 2026):
#   OpenAI  – https://openai.com/api/pricing/
#   Anthropic – https://docs.anthropic.com/en/docs/about-claude/pricing
_FALLBACK_PRICING = {
    # OpenAI – GPT-5 family
    "gpt-5.2":        {"input": 1.75,  "output": 14.00},
    "gpt-5":          {"input": 1.25,  "output": 10.00},
    "gpt-5-mini":     {"input": 0.30,  "output": 1.20},
    # OpenAI – GPT-4o family
    "gpt-4o":         {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":    {"input": 0.15,  "output": 0.60},
    # OpenAI – GPT-4.1 family
    "gpt-4.1":        {"input": 2.00,  "output": 8.00},
    "gpt-4.1-mini":   {"input": 0.40,  "output": 1.60},
    "gpt-4.1-nano":   {"input": 0.10,  "output": 0.40},
    # OpenAI – older
    "gpt-4-turbo":    {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo":  {"input": 0.50,  "output": 1.50},
    # OpenAI – o-series (reasoning)
    "o1":             {"input": 15.00, "output": 60.00},
    "o1-mini":        {"input": 1.10,  "output": 4.40},
    "o1-preview":     {"input": 15.00, "output": 60.00},
    "o3":             {"input": 0.40,  "output": 1.60},
    "o3-mini":        {"input": 1.10,  "output": 4.40},
    "o4-mini":        {"input": 1.10,  "output": 4.40},
    # Anthropic
    "claude-opus-4-6":           {"input": 5.00,  "output": 25.00},
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 1.00,  "output": 5.00},
    "claude-sonnet-4":           {"input": 3.00,  "output": 15.00},
    "claude-haiku-4":            {"input": 1.00,  "output": 5.00},
}

# ── In-memory cache ──────────────────────────────────────────────
_pricing = None   # dict  |  None
_pricing_ts = 0.0


def _normalize_model(raw_model: str) -> str:
    """Strip provider prefix: 'openai/gpt-4o' → 'gpt-4o'."""
    if "/" in raw_model:
        return raw_model.split("/", 1)[1]
    return raw_model


# ── Disk cache ───────────────────────────────────────────────────
def _load_cache(allow_stale=False) -> dict | None:
    try:
        if not os.path.exists(CACHE_FILE):
            return None
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not allow_stale:
            ts = data.get("_timestamp", 0)
            if time.time() - ts > CACHE_TTL:
                return None
        return data.get("pricing", None)
    except Exception:
        return None


def _save_cache(pricing: dict):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"_timestamp": time.time(), "pricing": pricing},
                      f, indent=2)
    except Exception as exc:
        logger.debug("Pricing cache save failed: %s", exc)


# ── Web fetch (best-effort) ─────────────────────────────────────
def _fetch_from_web() -> dict | None:
    """Try to scrape pricing from the OpenAI page.

    The page is a JS SPA so this will usually fail; the fallback covers us.
    """
    try:
        from modules.http_client import safe_get
        resp = safe_get(PRICING_URL, timeout=(5, 10))
        text = resp.text
        pricing = {}
        for pattern in [r"gpt-[\w.-]+", r"o\d+-?\w*"]:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                ctx = text[max(0, match.start() - 200):match.end() + 500]
                inp = re.search(
                    r"\$(\d+\.?\d*)\s*/?\s*1M\s*(?:input|in)", ctx, re.I)
                out = re.search(
                    r"\$(\d+\.?\d*)\s*/?\s*1M\s*(?:output|out)", ctx, re.I)
                if inp and out:
                    pricing[match.group().lower()] = {
                        "input": float(inp.group(1)),
                        "output": float(out.group(1)),
                    }
        return pricing if pricing else None
    except Exception as exc:
        logger.debug("OpenAI pricing fetch failed: %s", exc)
        return None


# ── Resolve best pricing dict ───────────────────────────────────
def _get_pricing() -> dict:
    global _pricing, _pricing_ts

    if _pricing and (time.time() - _pricing_ts) < CACHE_TTL:
        return _pricing

    # 1. Disk cache (fresh)
    cached = _load_cache()
    if cached:
        _pricing, _pricing_ts = cached, time.time()
        return _pricing

    # 2. Web fetch
    web = _fetch_from_web()
    if web:
        merged = dict(_FALLBACK_PRICING)
        merged.update(web)
        _save_cache(merged)
        _pricing, _pricing_ts = merged, time.time()
        return _pricing

    # 3. Stale disk cache
    stale = _load_cache(allow_stale=True)
    if stale:
        _pricing, _pricing_ts = stale, time.time()
        return _pricing

    # 4. Hardcoded fallback
    _pricing, _pricing_ts = dict(_FALLBACK_PRICING), time.time()
    return _pricing


# ── Public API ───────────────────────────────────────────────────
def get_model_cost(raw_model: str,
                   input_tokens: int,
                   output_tokens: int) -> float | None:
    """Return cost in USD or *None* if model is unknown."""
    model = _normalize_model(raw_model)
    pricing = _get_pricing()

    rates = pricing.get(model)
    if not rates:
        # Prefix match: 'gpt-4o-2024-11-20' → 'gpt-4o'
        for key in sorted(pricing, key=len, reverse=True):
            if model.startswith(key):
                rates = pricing[key]
                break
    if not rates:
        return None

    return (input_tokens * rates["input"] / 1_000_000
            + output_tokens * rates["output"] / 1_000_000)


def refresh_pricing():
    """Force-refresh (call from a background thread at startup)."""
    global _pricing, _pricing_ts
    _pricing, _pricing_ts = None, 0.0
    _get_pricing()
