"""User settings endpoints — per-user config CRUD."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.user import User
from config import DEFAULT_CONFIG
from backend.app.api import market as _market_module

router = APIRouter(prefix="/settings", tags=["settings"])

_PROMPT_KEYS = [
    "prompt", "chat_prompt", "charts_chat_prompt",
    "instrument_profile_prompt", "calendar_event_prompt", "market_assessment_prompt",
]


@router.get("/defaults")
async def get_prompt_defaults():
    """Return factory-default prompt values (no auth required — they are public constants)."""
    return {k: DEFAULT_CONFIG.get(k, "") for k in _PROMPT_KEYS}


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
    current = dict(user.config or {})
    # Handle api_keys: don't overwrite with masked values
    if "api_keys" in body:
        for k, v in body["api_keys"].items():
            if v and "*" not in v:
                current.setdefault("api_keys", {})[k] = v
        del body["api_keys"]
    current.update(body)
    user.config = current
    flag_modified(user, "config")
    await db.commit()
    # Wyczyść backend cache instrumentów jeśli lista się zmieniła
    if "instruments" in body:
        _market_module._inst_cache.pop(user.id, None)
    return {"status": "ok"}
