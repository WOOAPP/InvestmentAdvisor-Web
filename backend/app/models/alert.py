"""Alert model — mirrors desktop's `alerts` table."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    symbol: Mapped[str | None] = mapped_column(String(50), default=None)
    message: Mapped[str | None] = mapped_column(Text, default=None)
    seen: Mapped[bool] = mapped_column(Boolean, default=False)
