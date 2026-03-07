"""Market data schemas."""

from typing import Literal

from pydantic import BaseModel


class InstrumentData(BaseModel):
    symbol: str
    name: str
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: int | float | None = None
    high_5d: float | None = None
    low_5d: float | None = None
    sparkline: list[float] = []
    source: str = "yfinance"
    error: str | None = None


class SparklineRequest(BaseModel):
    symbol: str
    timeframe: Literal["1m", "5m", "15m", "1h", "24h", "72h"] = "1h"
    source: Literal["yfinance", "coingecko", "stooq"] = "yfinance"
