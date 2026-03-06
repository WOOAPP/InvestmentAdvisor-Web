"""Market data endpoints — wraps desktop's market_data.py module."""

import asyncio
import time
from datetime import datetime, timezone
from functools import partial

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.instrument_profile import InstrumentProfile
from backend.app.models.user import User
from backend.app.schemas.market import InstrumentData, SparklineRequest

from backend.app.services.market_data import (
    get_all_instruments,
    get_sparkline_by_timeframe,
)
from config import DEFAULT_INSTRUMENTS

router = APIRouter(prefix="/market", tags=["market"])


# ── Instrument search (Yahoo Finance) ─────────────────────────

class InstrumentSearchResult(BaseModel):
    symbol: str
    name: str
    type: str
    exchange: str


_YF_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
_YF_HEADERS = {"User-Agent": "Mozilla/5.0"}
_ALLOWED_TYPES = {"EQUITY", "ETF", "INDEX", "CURRENCY", "CRYPTOCURRENCY", "MUTUALFUND", "FUTURE"}


def _do_yf_search(q: str) -> list[dict]:
    resp = requests.get(
        _YF_SEARCH_URL,
        params={"q": q, "quotesCount": 10, "newsCount": 0, "enableFuzzyQuery": "false"},
        headers=_YF_HEADERS,
        timeout=5,
    )
    resp.raise_for_status()
    quotes = resp.json().get("quotes", [])
    results = []
    for item in quotes:
        qtype = item.get("quoteType", "")
        if qtype not in _ALLOWED_TYPES:
            continue
        symbol = item.get("symbol", "")
        name = item.get("shortname") or item.get("longname") or symbol
        if not symbol:
            continue
        results.append({
            "symbol": symbol,
            "name": name,
            "type": item.get("typeDisp", qtype),
            "exchange": item.get("exchange", ""),
        })
    return results


@router.get("/search", response_model=list[InstrumentSearchResult])
async def search_instruments(
    q: str = Query(..., min_length=1, max_length=50),
    user: User = Depends(get_current_user),
):
    """Search for instruments by symbol or name via Yahoo Finance."""
    try:
        results = await asyncio.to_thread(_do_yf_search, q)
    except Exception:
        return []
    return [InstrumentSearchResult(**r) for r in results]


# ── In-memory cache: per user, TTL 15 s ───────────────────────
_INST_TTL = 15.0  # seconds
_inst_cache: dict[int, tuple[list, float]] = {}  # user_id → (results, timestamp)


@router.get("/instruments", response_model=list[InstrumentData])
async def list_instruments(user: User = Depends(get_current_user)):
    """Fetch current prices for all user instruments."""
    now = time.monotonic()
    cached = _inst_cache.get(user.id)
    if cached and now - cached[1] < _INST_TTL:
        return cached[0]

    instruments_config = user.config.get("instruments", DEFAULT_INSTRUMENTS)
    # Run blocking I/O in thread pool
    data = await asyncio.to_thread(get_all_instruments, instruments_config)
    results = [InstrumentData(symbol=symbol, **d) for symbol, d in data.items()]
    _inst_cache[user.id] = (results, now)
    return results


@router.post("/sparkline", response_model=list[float])
async def sparkline(body: SparklineRequest, user: User = Depends(get_current_user)):
    """Fetch sparkline data for a symbol at a given timeframe."""
    fn = partial(get_sparkline_by_timeframe, body.symbol, body.timeframe, body.source)
    return await asyncio.to_thread(fn)


# ── Batch current prices for arbitrary symbols ─────────────────

class PricesRequest(BaseModel):
    symbols: list[str]


@router.post("/prices", response_model=dict[str, float | None])
async def get_prices(body: PricesRequest, user: User = Depends(get_current_user)):
    """Return current price (USD) for each requested symbol via yfinance."""
    symbols = [s.upper() for s in body.symbols if s][:30]
    if not symbols:
        return {}
    instruments_config = [
        {"symbol": s, "name": s, "category": "other", "source": "yfinance"}
        for s in symbols
    ]
    data = await asyncio.to_thread(get_all_instruments, instruments_config)
    result: dict[str, float | None] = {}
    for sym in symbols:
        entry = data.get(sym)
        if entry and not entry.get("error") and entry.get("price") is not None:
            result[sym] = entry["price"]
        else:
            result[sym] = None
    return result


# ── Instrument profiles ────────────────────────────────────────

class ProfileResponse(BaseModel):
    symbol: str
    profile_text: str
    created_at: str


class ProfileSaveRequest(BaseModel):
    profile_text: str


@router.get("/profile/{symbol}", response_model=ProfileResponse)
async def get_profile(
    symbol: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return cached instrument profile for the current user, or 404."""
    result = await db.execute(
        select(InstrumentProfile).where(
            InstrumentProfile.user_id == user.id,
            InstrumentProfile.symbol == symbol.upper(),
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileResponse(
        symbol=profile.symbol,
        profile_text=profile.profile_text,
        created_at=profile.created_at.isoformat(),
    )


@router.post("/profile/{symbol}", response_model=ProfileResponse)
async def save_profile(
    symbol: str,
    body: ProfileSaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update an instrument profile (upsert by user+symbol)."""
    sym = symbol.upper()
    result = await db.execute(
        select(InstrumentProfile).where(
            InstrumentProfile.user_id == user.id,
            InstrumentProfile.symbol == sym,
        )
    )
    existing = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.profile_text = body.profile_text
        existing.created_at = now
    else:
        db.add(InstrumentProfile(
            user_id=user.id,
            symbol=sym,
            profile_text=body.profile_text,
            created_at=now,
        ))
    await db.commit()
    return ProfileResponse(symbol=sym, profile_text=body.profile_text, created_at=now.isoformat())

import json as _json
import re as _re

from backend.app.api.reports import _merge_config
from modules.ai_engine import run_chat_with_usage


# ── Market Assessment (AI risk + opportunity) ──────────────────

class AssessmentRequest(BaseModel):
    context: str  # market context string (built by frontend buildChatContext)


class AssessmentResult(BaseModel):
    risk: int
    risk_reason: str
    opportunity: int
    opportunity_reason: str


@router.post("/assess", response_model=AssessmentResult)
async def assess_market(body: AssessmentRequest, user: User = Depends(get_current_user)):
    """Call AI to assess market risk and opportunity (1-10 each)."""
    config = _merge_config(user)
    system = config.get("market_assessment_prompt", "")

    messages = [{"role": "user", "content": body.context or "Brak danych rynkowych."}]
    reply, _ = await asyncio.to_thread(run_chat_with_usage, config, messages, system)

    # Extract JSON from reply (AI may wrap it in markdown)
    m = _re.search(r'{[^{}]+}', reply, _re.DOTALL)
    if not m:
        raise HTTPException(status_code=422, detail="AI response is not valid JSON")

    try:
        data = _json.loads(m.group())
    except _json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"JSON parse error: {exc}")

    return AssessmentResult(
        risk=max(1, min(10, int(data.get("risk", 5)))),
        risk_reason=str(data.get("risk_reason", "")),
        opportunity=max(1, min(10, int(data.get("opportunity", 5)))),
        opportunity_reason=str(data.get("opportunity_reason", "")),
    )
