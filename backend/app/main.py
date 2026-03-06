"""FastAPI application entry point."""

import asyncio
import logging
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
from backend.app.api import admin, auth, market, reports, portfolio, chat, settings as settings_api, calendar as calendar_api, stats as stats_api, news as news_api

logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Run Alembic migrations on startup so the DB schema is always current."""
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(os.path.join(_PROJECT_ROOT, "backend", "alembic.ini"))
        alembic_cfg.set_main_option(
            "script_location", os.path.join(_PROJECT_ROOT, "backend", "alembic")
        )
        alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied successfully")
    except Exception:
        logger.exception("Failed to run Alembic migrations")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run in a thread so Alembic's asyncio.run() gets a clean event loop
    await asyncio.to_thread(_run_migrations)
    yield


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
app.include_router(calendar_api.router, prefix="/api")
app.include_router(stats_api.router, prefix="/api")
app.include_router(news_api.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
