"""Chat endpoints — wraps desktop's ai_engine.run_chat_with_usage()."""

import asyncio
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db, async_session
from backend.app.core.deps import get_current_user
from backend.app.models.activity_log import ActivityLog
from backend.app.models.user import User
from backend.app.models.token_usage import TokenUsage
from backend.app.api.reports import _merge_config
from backend.app.services.pricing import calculate_cost

from modules.ai_engine import run_chat_with_usage
from modules.calendar_data import fetch_calendar_14d, format_calendar_for_ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    system_prompt: str = ""
    request_type: str = "chat"


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, user: User = Depends(get_current_user)):
    config = _merge_config(user)
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    system = body.system_prompt or config.get("chat_prompt", "")

    # Append upcoming-week macroeconomic calendar to system prompt
    try:
        cal_events, _ = await asyncio.to_thread(fetch_calendar_14d)
        calendar_text = format_calendar_for_ai(cal_events, days=7)
        if calendar_text:
            system = (system + "\n\n" + calendar_text) if system else calendar_text
    except Exception as e:
        logger.warning("Calendar fetch for chat failed: %s", e)

    reply, usage = await asyncio.to_thread(run_chat_with_usage, config, messages, system)

    # Log token usage (fire-and-forget)
    asyncio.ensure_future(_log_usage(user.id, usage, body.request_type))

    return ChatResponse(reply=reply)


async def _log_usage(user_id: int, usage: dict, request_type: str) -> None:
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    if inp == 0 and out == 0:
        return
    provider = usage.get("provider", "unknown")
    model = usage.get("model", "unknown")
    cost = calculate_cost(provider, model, inp, out)
    try:
        async with async_session() as db:
            db.add(TokenUsage(
                user_id=user_id,
                provider=provider,
                model=model,
                input_tokens=inp,
                output_tokens=out,
                cost_usd=cost,
                request_type=request_type,
            ))
            db.add(ActivityLog(user_id=user_id, action=request_type, detail=f"{provider}/{model}"))
            await db.commit()
    except Exception:
        logger.exception("Failed to log token usage for user %d", user_id)
