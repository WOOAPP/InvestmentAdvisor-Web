"""Market data endpoints — wraps desktop's market_data.py module."""

import asyncio
from functools import partial

from fastapi import APIRouter, Depends

from backend.app.core.deps import get_current_user
from backend.app.models.user import User
from backend.app.schemas.market import InstrumentData, SparklineRequest

# Import desktop business logic directly
from modules.market_data import (
    get_all_instruments,
    get_sparkline_by_timeframe,
)
from config import DEFAULT_INSTRUMENTS

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/instruments", response_model=list[InstrumentData])
async def list_instruments(user: User = Depends(get_current_user)):
    """Fetch current prices for all user instruments."""
    instruments_config = user.config.get("instruments", DEFAULT_INSTRUMENTS)
    # Run blocking I/O in thread pool
    data = await asyncio.to_thread(get_all_instruments, instruments_config)
    results = []
    for symbol, d in data.items():
        results.append(InstrumentData(symbol=symbol, **d))
    return results


@router.post("/sparkline", response_model=list[float])
async def sparkline(body: SparklineRequest, user: User = Depends(get_current_user)):
    """Fetch sparkline data for a symbol at a given timeframe."""
    fn = partial(get_sparkline_by_timeframe, body.symbol, body.timeframe, body.source)
    return await asyncio.to_thread(fn)
