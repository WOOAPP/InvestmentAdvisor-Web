"""Stats endpoint — token usage aggregates (session + historical)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from backend.app.services.constants import APP_TIMEZONE
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.token_usage import TokenUsage
from backend.app.models.user import User

router = APIRouter(prefix="/stats", tags=["stats"])


async def _aggregate(db: AsyncSession, user_id: int, since: datetime | None = None):
    q = select(
        func.coalesce(func.sum(TokenUsage.input_tokens), 0),
        func.coalesce(func.sum(TokenUsage.output_tokens), 0),
        func.coalesce(func.sum(TokenUsage.cost_usd), 0.0),
        func.count(TokenUsage.id),
    ).where(TokenUsage.user_id == user_id)
    if since:
        q = q.where(TokenUsage.created_at >= since)
    row = (await db.execute(q)).one()
    return {
        "input_tokens": int(row[0]),
        "output_tokens": int(row[1]),
        "cost_usd": float(row[2]),
        "requests": int(row[3]),
    }


async def _aggregate_by_type(db: AsyncSession, user_id: int, since: datetime | None = None):
    q = select(
        TokenUsage.request_type,
        func.coalesce(func.sum(TokenUsage.input_tokens), 0),
        func.coalesce(func.sum(TokenUsage.output_tokens), 0),
        func.coalesce(func.sum(TokenUsage.cost_usd), 0.0),
        func.count(TokenUsage.id),
    ).where(TokenUsage.user_id == user_id).group_by(TokenUsage.request_type)
    if since:
        q = q.where(TokenUsage.created_at >= since)
    rows = (await db.execute(q)).all()
    return {
        row[0]: {
            "input_tokens": int(row[1]),
            "output_tokens": int(row[2]),
            "cost_usd": float(row[3]),
            "requests": int(row[4]),
        }
        for row in rows
    }


@router.get("")
async def get_stats(
    session_since: str | None = Query(None, description="ISO datetime of login (for session stats)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return token usage aggregates — historical total and optionally session."""
    session_dt: datetime | None = None
    if session_since:
        try:
            session_dt = datetime.fromisoformat(session_since)
            if session_dt.tzinfo is None:
                session_dt = session_dt.replace(tzinfo=APP_TIMEZONE)
        except ValueError:
            session_dt = None

    historical = await _aggregate(db, user.id)
    historical_by_type = await _aggregate_by_type(db, user.id)

    session = None
    session_by_type = None
    if session_dt:
        session = await _aggregate(db, user.id, since=session_dt)
        session_by_type = await _aggregate_by_type(db, user.id, since=session_dt)

    return {
        "historical": {**historical, "by_type": historical_by_type},
        "session": {**session, "by_type": session_by_type} if session else None,
    }
