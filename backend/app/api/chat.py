"""Chat endpoints — wraps desktop's ai_engine.run_chat()."""

import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.core.deps import get_current_user
from backend.app.models.user import User
from backend.app.api.reports import _merge_config

from modules.ai_engine import run_chat

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    system_prompt: str = ""


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, user: User = Depends(get_current_user)):
    config = _merge_config(user)
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    system = body.system_prompt or config.get("chat_prompt", "")
    reply = await asyncio.to_thread(run_chat, config, messages, system)
    return ChatResponse(reply=reply)
