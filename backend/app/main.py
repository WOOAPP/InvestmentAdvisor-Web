"""FastAPI application entry point."""

import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to sys.path so desktop modules (modules/, config.py, constants.py)
# are importable without modification.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.app.core.config import settings
from backend.app.api import auth, market, reports, portfolio, chat, settings as settings_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: could initialize scheduler, warm caches, etc.
    yield
    # Shutdown: cleanup


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
