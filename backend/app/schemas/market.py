"""Market data schemas."""

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
    timeframe: str = "1h"
    source: str = "yfinance"
