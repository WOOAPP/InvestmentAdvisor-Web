"""Economic calendar endpoint."""

import asyncio
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.core.deps import get_current_user
from backend.app.models.user import User
from backend.app.api.reports import _merge_config
from backend.app.api.chat import _log_usage
from modules.calendar_data import fetch_calendar_14d
from modules.ai_engine import run_chat_with_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])


class CalendarEvent(BaseModel):
    date: str
    time: str
    flag: str
    country: str
    event: str
    impact_icon: str
    impact_label: str
    impact_raw: str
    forecast: str
    previous: str
    significance: str


class CalendarResponse(BaseModel):
    events: list[CalendarEvent]
    error: str | None = None


class AnalyzeEventRequest(BaseModel):
    event: str
    country: str
    date: str
    time: str
    impact_raw: str
    forecast: str
    previous: str
    significance: str


class AnalyzeEventResponse(BaseModel):
    analysis: str


@router.get("", response_model=CalendarResponse)
async def get_calendar(user: User = Depends(get_current_user)):
    """Return economic calendar events for today + next 14 days."""
    events, err = await asyncio.to_thread(fetch_calendar_14d)
    return CalendarResponse(events=[CalendarEvent(**e) for e in events], error=err)


@router.post("/analyze", response_model=AnalyzeEventResponse)
async def analyze_event(body: AnalyzeEventRequest, user: User = Depends(get_current_user)):
    """Generate AI analysis for a single calendar event."""
    config = _merge_config(user)
    system_prompt = config.get("calendar_event_prompt", "")

    user_message = (
        f"Wydarzenie: {body.event}\n"
        f"Kraj: {body.country}\n"
        f"Data: {body.date} {body.time}\n"
        f"Waga: {body.impact_raw}\n"
        f"Prognoza: {body.forecast or 'brak'}\n"
        f"Poprzednio: {body.previous or 'brak'}\n"
        f"Znaczenie (opis źródłowy): {body.significance or 'brak'}"
    )

    messages = [{"role": "user", "content": user_message}]
    reply, usage = await asyncio.to_thread(run_chat_with_usage, config, messages, system_prompt)

    asyncio.ensure_future(_log_usage(user.id, usage, "calendar_event"))

    return AnalyzeEventResponse(analysis=reply)
