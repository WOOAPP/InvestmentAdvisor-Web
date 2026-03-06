"""Admin panel endpoints — users, activity, token usage."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.deps import get_admin_user
from backend.app.models.activity_log import ActivityLog
from backend.app.models.token_usage import TokenUsage
from backend.app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """All users with last login, action count, and token stats."""
    # Base user info
    users_result = await db.execute(
        select(User).order_by(User.created_at)
    )
    users = users_result.scalars().all()

    # Last login per user
    last_login_q = (
        select(
            ActivityLog.user_id,
            func.max(ActivityLog.created_at).label("last_login"),
        )
        .where(ActivityLog.action == "login")
        .group_by(ActivityLog.user_id)
    )
    last_login_rows = (await db.execute(last_login_q)).all()
    last_login_map = {row.user_id: row.last_login for row in last_login_rows}

    # Action count per user
    action_count_q = (
        select(
            ActivityLog.user_id,
            func.count(ActivityLog.id).label("action_count"),
        )
        .group_by(ActivityLog.user_id)
    )
    action_count_rows = (await db.execute(action_count_q)).all()
    action_count_map = {row.user_id: row.action_count for row in action_count_rows}

    # Token usage per user
    token_q = (
        select(
            TokenUsage.user_id,
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(TokenUsage.cost_usd), 0.0).label("cost_usd"),
            func.count(TokenUsage.id).label("requests"),
        )
        .group_by(TokenUsage.user_id)
    )
    token_rows = (await db.execute(token_q)).all()
    token_map = {
        row.user_id: {
            "input_tokens": int(row.input_tokens),
            "output_tokens": int(row.output_tokens),
            "cost_usd": float(row.cost_usd),
            "requests": int(row.requests),
        }
        for row in token_rows
    }

    result = []
    for u in users:
        tokens = token_map.get(u.id, {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "requests": 0})
        result.append({
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": last_login_map.get(u.id, u.created_at).isoformat() if last_login_map.get(u.id, u.created_at) else None,
            "action_count": action_count_map.get(u.id, 0),
            "tokens": tokens,
        })

    return result


@router.get("/activity")
async def recent_activity(
    limit: int = 50,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Recent activity across all users."""
    q = (
        select(
            ActivityLog.id,
            ActivityLog.user_id,
            ActivityLog.action,
            ActivityLog.detail,
            ActivityLog.ip_address,
            ActivityLog.created_at,
            User.email,
            User.display_name,
        )
        .join(User, ActivityLog.user_id == User.id)
        .order_by(desc(ActivityLog.created_at))
        .limit(min(limit, 200))
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "email": r.email,
            "display_name": r.display_name,
            "action": r.action,
            "detail": r.detail,
            "ip_address": r.ip_address,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/stats")
async def global_stats(
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Global token usage summary."""
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    token_q = select(
        func.coalesce(func.sum(TokenUsage.input_tokens), 0),
        func.coalesce(func.sum(TokenUsage.output_tokens), 0),
        func.coalesce(func.sum(TokenUsage.cost_usd), 0.0),
        func.count(TokenUsage.id),
    )
    row = (await db.execute(token_q)).one()

    total_actions = (await db.execute(select(func.count(ActivityLog.id)))).scalar() or 0

    return {
        "total_users": total_users,
        "total_actions": total_actions,
        "tokens": {
            "input_tokens": int(row[0]),
            "output_tokens": int(row[1]),
            "cost_usd": float(row[2]),
            "requests": int(row[3]),
        },
    }
