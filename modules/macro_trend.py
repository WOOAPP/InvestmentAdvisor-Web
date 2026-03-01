"""
Macro-Trend Engine — orchestrator that combines C1-C5 into a single
structured payload ready for the LLM.

Entry point: build_macro_payload(api_key, ...) -> dict
"""

import json
import logging

from modules.news_store import (
    fetch_all_windows, store_news, get_news_since, get_news_in_range,
    cleanup_old_news,
)
from modules.news_classifier import classify_articles
from modules.news_of_day import select_news_of_day
from modules.trend_narrative import build_trend_payload, build_geo_24h

logger = logging.getLogger(__name__)

# Max articles sent to LLM per window (controls input size)
MAX_24H_TO_LLM = 20
MAX_LONGER_WINDOW = 50  # 7/30/90 used only for aggregation, not raw


def build_macro_payload(api_key: str, **kwargs) -> dict:
    """
    Full pipeline:
      1. Fetch news for all windows (NewsAPI)
      2. Classify region + topic
      3. Store in SQLite
      4. Build news-of-day
      5. Build geo 24h
      6. Build trend 7/30/90
      7. Return structured payload

    Returns dict ready to be serialized into the LLM prompt.
    """
    # ── 1. Fetch & deduplicate ──────────────────────────────────
    raw_articles = fetch_all_windows(api_key, **kwargs)
    logger.info("Fetched %d deduplicated articles across all windows",
                len(raw_articles))

    # ── 2. Classify ─────────────────────────────────────────────
    classify_articles(raw_articles)

    # ── 3. Store ────────────────────────────────────────────────
    store_news(raw_articles)
    cleanup_old_news(days=100)

    # ── 4. Split by time range (from DB for completeness) ──────
    articles_24h = get_news_since(hours=72)  # 24-72h window
    classify_articles(articles_24h)  # re-classify DB rows missing region/topic

    articles_7d = get_news_in_range(days_from=7, days_to=0,
                                    limit=MAX_LONGER_WINDOW)
    classify_articles(articles_7d)

    articles_30d = get_news_in_range(days_from=30, days_to=0,
                                     limit=MAX_LONGER_WINDOW)
    classify_articles(articles_30d)

    articles_90d = get_news_in_range(days_from=90, days_to=0,
                                     limit=MAX_LONGER_WINDOW)
    classify_articles(articles_90d)

    # ── 5. News of the day ──────────────────────────────────────
    news_of_day = select_news_of_day(articles_24h)

    # ── 6. Geo 24h ──────────────────────────────────────────────
    geo_24h = build_geo_24h(articles_24h)

    # ── 7. Trend narracji ───────────────────────────────────────
    trend = build_trend_payload(
        articles_24h, articles_7d, articles_30d, articles_90d)

    # ── 8. Assemble payload ─────────────────────────────────────
    # Truncate 24h articles for LLM (top 20 by recency)
    articles_24h_limited = articles_24h[:MAX_24H_TO_LLM]

    payload = {
        "news_dnia": news_of_day,
        "geo_24h": _summarize_geo(geo_24h),
        "articles_24h": _slim_articles(articles_24h_limited),
        "trend": _slim_trend(trend),
        "stats": {
            "total_fetched": len(raw_articles),
            "articles_24h": len(articles_24h),
            "articles_7d": len(articles_7d),
            "articles_30d": len(articles_30d),
            "articles_90d": len(articles_90d),
        },
    }
    return payload


def _slim_articles(articles: list[dict]) -> list[dict]:
    """Keep only fields needed by LLM to save tokens."""
    slim = []
    for a in articles:
        slim.append({
            "title": a.get("title", ""),
            "source": a.get("source", ""),
            "published_at": a.get("published_at", "")[:16],
            "region": a.get("region", ""),
            "topic": a.get("topic", ""),
            "description": (a.get("description") or "")[:120],
        })
    return slim


def _summarize_geo(geo: dict) -> dict:
    """Summarize geo breakdown for LLM — max 5 articles per region."""
    summary = {}
    for region, articles in geo.items():
        summary[region] = [
            {
                "title": a.get("title", ""),
                "source": a.get("source", ""),
                "topic": a.get("topic", ""),
            }
            for a in articles[:5]
        ]
    return summary


def _slim_trend(trend: dict) -> dict:
    """Keep trend payload compact for LLM."""
    # Aggregates: only top 3 regions/topics per window
    slim_agg = {}
    for window, agg in trend.get("aggregates", {}).items():
        slim_agg[window] = {
            "count": agg.get("count", 0),
            "top_regions": agg.get("top_regions", [])[:3],
            "top_topics": agg.get("top_topics", [])[:3],
            "top_keywords": agg.get("top_keywords", [])[:5],
        }
    return {
        "aggregates": slim_agg,
        "diffs": trend.get("diffs", []),
    }


def format_macro_payload_for_llm(payload: dict) -> str:
    """
    Convert the structured payload into a text block for the LLM prompt.
    Keeps it concise but structured.
    """
    parts = []

    # ── News dnia ───────────────────────────────────────────────
    nod = payload.get("news_dnia")
    if nod:
        sel = nod.get("selected_news", {})
        parts.append("=== NEWS DNIA ===")
        parts.append(f"Tytuł: {sel.get('title', 'brak')}")
        parts.append(f"Źródło: {sel.get('source', '')} | "
                     f"Region: {sel.get('region', '')} | "
                     f"Temat: {sel.get('topic', '')}")
        parts.append(f"Score: {nod.get('score', 0)}")
        parts.append("Uzasadnienie:")
        for j in nod.get("justification", []):
            parts.append(f"  - {j}")
        parts.append("Co obserwować:")
        for s in nod.get("watch_signals", []):
            parts.append(f"  - {s}")
        parts.append("")

    # ── Geo 24h ─────────────────────────────────────────────────
    geo = payload.get("geo_24h", {})
    if geo:
        parts.append("=== GEO 24H (per region) ===")
        for region, articles in geo.items():
            titles = [a.get("title", "") for a in articles]
            parts.append(f"\n[{region}] ({len(titles)} news)")
            for t in titles[:3]:
                parts.append(f"  - {t[:100]}")
        parts.append("")

    # ── Top 24h articles ────────────────────────────────────────
    arts = payload.get("articles_24h", [])
    if arts:
        parts.append(f"=== NEWSY 24-72H (top {len(arts)}) ===")
        for i, a in enumerate(arts[:15], 1):
            parts.append(
                f"{i}. [{a.get('source','')}] {a.get('title','')}"
                f" | {a.get('region','')} | {a.get('topic','')}")
            if a.get("description"):
                parts.append(f"   {a['description']}")
        parts.append("")

    # ── Trend ───────────────────────────────────────────────────
    trend = payload.get("trend", {})
    aggs = trend.get("aggregates", {})
    if aggs:
        parts.append("=== TREND NARRACJI ===")
        for window in ("24h", "7d", "30d", "90d"):
            agg = aggs.get(window, {})
            if not agg.get("count"):
                continue
            regions = ", ".join(
                f"{r['region']}({r['count']})"
                for r in agg.get("top_regions", []))
            topics = ", ".join(
                f"{t['topic']}({t['count']})"
                for t in agg.get("top_topics", []))
            kws = ", ".join(agg.get("top_keywords", []))
            parts.append(
                f"[{window}] {agg['count']} art. | "
                f"regiony: {regions} | tematy: {topics} | "
                f"keywords: {kws}")
        parts.append("")

    diffs = trend.get("diffs", [])
    if diffs:
        parts.append("Porównanie trendów:")
        for d in diffs:
            det = d.get("details", {})
            parts.append(
                f"  {d['window']}: {d['signal']}"
                f" (temat 24h: {det.get('dominant_topic_24h', '?')}"
                f" vs okno: {det.get('dominant_topic_window', '?')})")
            new_kw = det.get("new_keywords", [])
            if new_kw:
                parts.append(f"    Nowe keywords: {', '.join(new_kw)}")
        parts.append("")

    return "\n".join(parts)
