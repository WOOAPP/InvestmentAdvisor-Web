"""Portfolio model — mirrors desktop's `portfolio` table."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class PortfolioPosition(Base):
    __tablename__ = "portfolio"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100), default="")
    quantity: Mapped[float] = mapped_column(Float)
    buy_price: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    buy_currency: Mapped[str] = mapped_column(String(10), default="USD")
    buy_fx_to_usd: Mapped[float] = mapped_column(Float, default=1.0)
    buy_price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tab_type: Mapped[str] = mapped_column(String(20), default="zakupione")
