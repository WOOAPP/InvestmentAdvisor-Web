"""Report schemas."""

from datetime import datetime

from pydantic import BaseModel


class ReportSummary(BaseModel):
    id: int
    created_at: datetime
    provider: str | None
    model: str | None
    risk_level: int
    preview: str | None = None

    model_config = {"from_attributes": True}


class ReportDetail(BaseModel):
    id: int
    created_at: datetime
    provider: str | None
    model: str | None
    market_summary: str | None
    analysis: str | None
    risk_level: int
    input_tokens: int
    output_tokens: int

    model_config = {"from_attributes": True}
