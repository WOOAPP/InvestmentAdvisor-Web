"""Portfolio schemas."""

from datetime import datetime

from pydantic import BaseModel


class PositionCreate(BaseModel):
    symbol: str
    name: str = ""
    quantity: float
    buy_price: float
    buy_currency: str = "USD"
    buy_fx_to_usd: float = 1.0
    tab_type: str = "zakupione"


class PositionResponse(BaseModel):
    id: int
    symbol: str
    name: str
    quantity: float
    buy_price: float
    created_at: datetime
    buy_currency: str
    buy_fx_to_usd: float
    buy_price_usd: float
    tab_type: str

    model_config = {"from_attributes": True}
