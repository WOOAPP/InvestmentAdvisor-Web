"""News title rewriting — uses a cheap nano LLM to create catchy Polish headlines."""

import asyncio
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.core.database import async_session
from backend.app.core.deps import get_current_user
from backend.app.models.user import User
from backend.app.models.token_usage import TokenUsage
from backend.app.api.reports import _merge_config
from backend.app.services.pricing import calculate_cost

from config import get_api_key
from modules.ai_engine import _call_provider, _PROVIDER_DEFAULTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])

_REWRITE_MODEL = "gpt-4.1-nano"
_REWRITE_PROVIDER = "openai"

_SYSTEM_PROMPT = (
    "Jestes redaktorem wiadomosci finansowych. "
    "Otrzymasz liste tytulow newsow (po jednym w linii). "
    "Dla kazdego tytulu napisz chwytliwy, zwiezly naglowek po polsku (maks 80 znakow). "
    "Zachowaj sens i kluczowe fakty. Uzyj mocnych czasownikow. "
    "Odpowiedz TYLKO lista przepisanych tytulow — po jednym w linii, w tej samej kolejnosci. "
    "Bez numeracji, bez dodatkowego tekstu."
)


class RewriteRequest(BaseModel):
    titles: list[str]


class RewriteResponse(BaseModel):
    titles: list[str]


@router.post("/rewrite-titles", response_model=RewriteResponse)
async def rewrite_titles(body: RewriteRequest, user: User = Depends(get_current_user)):
    if not body.titles:
        return RewriteResponse(titles=[])

    config = _merge_config(user)

    # Use OpenAI nano if key available, otherwise skip rewriting
    api_key = get_api_key(config, _PROVIDER_DEFAULTS[_REWRITE_PROVIDER]["key"])
    if not api_key:
        # Fallback: return originals
        return RewriteResponse(titles=body.titles)

    user_msg = "\n".join(body.titles)

    try:
        text, usage = await asyncio.to_thread(
            _call_provider,
            _REWRITE_PROVIDER,
            api_key,
            _REWRITE_MODEL,
            _SYSTEM_PROMPT,
            [{"role": "user", "content": user_msg}],
            512,
        )

        rewritten = [line.strip() for line in text.strip().split("\n") if line.strip()]

        # If LLM returned wrong count, fall back to originals
        if len(rewritten) != len(body.titles):
            logger.warning(
                "Rewrite returned %d titles, expected %d — using originals",
                len(rewritten), len(body.titles),
            )
            rewritten = body.titles

        # Log usage (fire-and-forget)
        asyncio.ensure_future(_log_usage(user.id, usage))

        return RewriteResponse(titles=rewritten)

    except Exception:
        logger.exception("News title rewrite failed")
        return RewriteResponse(titles=body.titles)


async def _log_usage(user_id: int, usage) -> None:
    if not usage:
        return
    inp = getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0
    out = getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0) or 0
    if inp == 0 and out == 0:
        return
    cost = calculate_cost(_REWRITE_PROVIDER, _REWRITE_MODEL, inp, out)
    try:
        async with async_session() as db:
            db.add(TokenUsage(
                user_id=user_id,
                provider=_REWRITE_PROVIDER,
                model=_REWRITE_MODEL,
                input_tokens=inp,
                output_tokens=out,
                cost_usd=cost,
                request_type="news_rewrite",
            ))
            await db.commit()
    except Exception:
        logger.exception("Failed to log news rewrite usage for user %d", user_id)
