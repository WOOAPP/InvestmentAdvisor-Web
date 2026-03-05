"""Report endpoints — list, detail, run analysis, delete."""

import asyncio
import logging
from functools import partial

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.report import Report
from backend.app.models.user import User
from backend.app.schemas.report import ReportDetail, ReportSummary

# Desktop business logic
from config import DEFAULT_CONFIG, get_api_key
from modules.ai_engine import run_analysis
from modules.market_data import get_all_instruments, format_market_summary
from modules.scraper import scrape_all
from modules.macro_trend import build_macro_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


def _merge_config(user: User) -> dict:
    """Merge user config over default config (like desktop's load_config)."""
    merged = {**DEFAULT_CONFIG, **(user.config or {})}
    # Ensure api_keys sub-dict is merged properly
    default_keys = DEFAULT_CONFIG.get("api_keys", {})
    user_keys = (user.config or {}).get("api_keys", {})
    merged["api_keys"] = {**default_keys, **user_keys}
    return merged


@router.get("", response_model=list[ReportSummary])
async def list_reports(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            Report.id,
            Report.created_at,
            Report.provider,
            Report.model,
            Report.risk_level,
            func.substr(Report.analysis, 1, 200).label("preview"),
        )
        .where(Report.user_id == user.id)
        .order_by(Report.created_at.desc())
        .limit(limit)
    )
    return [ReportSummary.model_validate(row._mapping) for row in result]


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return report


@router.post("/run", status_code=202)
async def run_analysis_endpoint(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start an analysis in the background. Returns immediately."""
    config = _merge_config(user)
    background_tasks.add_task(_run_analysis_task, user.id, config)
    return {"status": "analysis_started"}


async def _run_analysis_task(user_id: int, config: dict):
    """Background task that runs the full analysis pipeline."""
    try:
        instruments_config = config.get("instruments", [])
        # Fetch market data (blocking I/O)
        market_data = await asyncio.to_thread(get_all_instruments, instruments_config)
        market_summary = await asyncio.to_thread(
            format_market_summary, market_data
        )

        # Build macro payload (expects newsdata API key string, not config dict)
        macro_text = ""
        try:
            newsdata_key = get_api_key(config, "newsdata")
            macro_result = {}
            if newsdata_key:
                macro_result = await asyncio.to_thread(
                    partial(build_macro_payload, newsdata_key)
                )
            if isinstance(macro_result, dict):
                macro_text = macro_result.get("llm_payload", "")
        except Exception as e:
            logger.warning("Macro payload build failed: %s", e)

        # Scrape sources
        scraped_text = ""
        sources = config.get("sources", [])
        if sources:
            trusted = config.get("trusted_domains")
            scraped_text = await asyncio.to_thread(
                scrape_all, sources[:20], trusted_domains=trusted
            )

        # Run AI analysis (blocking)
        result = await asyncio.to_thread(
            run_analysis, config, market_summary, [],
            scraped_text, macro_text, market_data
        )

        # Save to DB
        from backend.app.core.database import async_session
        async with async_session() as db:
            risk_level = 0
            text = result.get("text", "") if isinstance(result, dict) else str(result)
            report = Report(
                user_id=user_id,
                provider=config.get("ai_provider"),
                model=config.get("ai_model"),
                market_summary=market_summary,
                analysis=text,
                risk_level=risk_level,
                input_tokens=result.get("input_tokens", 0) if isinstance(result, dict) else 0,
                output_tokens=result.get("output_tokens", 0) if isinstance(result, dict) else 0,
            )
            db.add(report)
            await db.commit()
            logger.info("Analysis complete for user %d, report saved", user_id)
    except Exception:
        logger.exception("Analysis task failed for user %d", user_id)


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    await db.delete(report)
    await db.commit()
