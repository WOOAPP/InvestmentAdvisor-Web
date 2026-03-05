"""User settings endpoints — per-user config CRUD."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.user import User
from config import DEFAULT_CONFIG

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings(user: User = Depends(get_current_user)):
    """Return user config merged with defaults. API keys are masked."""
    merged = {**DEFAULT_CONFIG, **(user.config or {})}
    # Mask API keys in response
    keys = merged.get("api_keys", {})
    masked = {}
    for k, v in keys.items():
        if v and len(v) > 4:
            masked[k] = v[:4] + "*" * min(len(v) - 4, 12)
        else:
            masked[k] = "****" if v else ""
    merged["api_keys"] = masked
    return merged


@router.put("")
async def update_settings(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user config. Merges with existing config."""
    current = user.config or {}
    # Handle api_keys: don't overwrite with masked values
    if "api_keys" in body:
        for k, v in body["api_keys"].items():
            if v and "*" not in v:
                current.setdefault("api_keys", {})[k] = v
        del body["api_keys"]
    current.update(body)
    user.config = current
    await db.commit()
    return {"status": "ok"}
