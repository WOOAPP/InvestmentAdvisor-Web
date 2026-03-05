"""Market snapshot model — mirrors desktop's `market_snapshots` table."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    symbol: Mapped[str] = mapped_column(String(50))
    name: Mapped[str | None] = mapped_column(String(100), default=None)
    price: Mapped[float | None] = mapped_column(Float, default=None)
    change_pct: Mapped[float | None] = mapped_column(Float, default=None)
