"""
C5: Trend narracji — structured aggregates for 7d/30d/90d windows
compared against the 24h baseline.

Output is a structured payload (dict), not long text.
"""

import re
from collections import Counter


def _extract_keywords(articles: list[dict], top_n: int = 10) -> list[str]:
    """Extract top keywords from article titles (simple word freq)."""
    stopwords = {
        "the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
        "or", "is", "are", "was", "were", "be", "been", "has", "have",
        "had", "with", "from", "by", "as", "it", "its", "this", "that",
        "but", "not", "no", "will", "would", "can", "could", "may",
        "new", "says", "said", "after", "over", "into", "about",
        "than", "more", "up", "out", "also", "just", "how", "what",
        "when", "where", "who", "all", "their", "his", "her", "he",
        "she", "they", "we", "you", "i", "my", "your", "do", "does",
        "did", "if", "so", "get", "got", "one", "two",
        # Polish stopwords
        "w", "na", "i", "z", "do", "się", "nie", "o", "po", "za",
        "to", "ze", "od", "jest", "dla", "jak", "co", "ale",
    }
    word_counter: Counter = Counter()
    for art in articles:
        title = art.get("title", "")
        words = re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}", title.lower())
        for w in words:
            if w not in stopwords:
                word_counter[w] += 1
    return [w for w, _ in word_counter.most_common(top_n)]


def _aggregate_window(articles: list[dict]) -> dict:
    """Build aggregate stats for a set of articles."""
    if not articles:
        return {
            "count": 0,
            "top_regions": [],
            "top_topics": [],
            "top_keywords": [],
        }

    region_counter: Counter = Counter()
    topic_counter: Counter = Counter()
    for art in articles:
        region_counter[art.get("region", "Świat")] += 1
        topic_counter[art.get("topic", "inne")] += 1

    return {
        "count": len(articles),
        "top_regions": [
            {"region": r, "count": c}
            for r, c in region_counter.most_common(6)
        ],
        "top_topics": [
            {"topic": t, "count": c}
            for t, c in topic_counter.most_common(8)
        ],
        "top_keywords": _extract_keywords(articles, top_n=10),
    }


def _compare_windows(baseline: dict, comparison: dict,
                     label: str) -> dict:
    """
    Compare a longer window aggregate vs 24h baseline.
    Returns diff description: continuation / anomaly / possible turning point.
    """
    if not baseline.get("count") or not comparison.get("count"):
        return {
            "window": label,
            "signal": "brak danych",
            "details": {},
        }

    base_topics = {t["topic"]: t["count"] for t in baseline.get("top_topics", [])}
    comp_topics = {t["topic"]: t["count"] for t in comparison.get("top_topics", [])}

    base_regions = {r["region"]: r["count"] for r in baseline.get("top_regions", [])}
    comp_regions = {r["region"]: r["count"] for r in comparison.get("top_regions", [])}

    # Determine signal type
    base_top_topic = max(base_topics, key=base_topics.get) if base_topics else None
    comp_top_topic = max(comp_topics, key=comp_topics.get) if comp_topics else None

    base_top_region = max(base_regions, key=base_regions.get) if base_regions else None
    comp_top_region = max(comp_regions, key=comp_regions.get) if comp_regions else None

    # New topics in 24h that weren't dominant before
    new_topics = [t for t in base_topics if t not in comp_topics
                  or (comp_topics.get(t, 0) / max(comparison["count"], 1))
                  < (base_topics[t] / max(baseline["count"], 1)) * 0.5]

    # Determine overall signal
    if base_top_topic == comp_top_topic and base_top_region == comp_top_region:
        signal = "kontynuacja"
    elif new_topics:
        signal = "możliwy punkt zwrotny"
    else:
        signal = "anomalia"

    # Build base keywords for comparison
    base_kw = set(baseline.get("top_keywords", []))
    comp_kw = set(comparison.get("top_keywords", []))
    new_keywords = list(base_kw - comp_kw)[:5]
    gone_keywords = list(comp_kw - base_kw)[:5]

    return {
        "window": label,
        "signal": signal,
        "details": {
            "dominant_topic_24h": base_top_topic,
            "dominant_topic_window": comp_top_topic,
            "dominant_region_24h": base_top_region,
            "dominant_region_window": comp_top_region,
            "new_topics_in_24h": new_topics[:5],
            "new_keywords": new_keywords,
            "fading_keywords": gone_keywords,
        },
    }


def build_trend_payload(articles_24h: list[dict],
                        articles_7d: list[dict],
                        articles_30d: list[dict],
                        articles_90d: list[dict]) -> dict:
    """
    Build the complete trend narrative payload.

    Returns:
        {
            "aggregates": {
                "24h": { count, top_regions, top_topics, top_keywords },
                "7d":  { ... },
                "30d": { ... },
                "90d": { ... },
            },
            "diffs": [
                { "window": "7d vs 24h", "signal": ..., "details": ... },
                { "window": "30d vs 24h", ... },
                { "window": "90d vs 24h", ... },
            ]
        }
    """
    agg_24h = _aggregate_window(articles_24h)
    agg_7d = _aggregate_window(articles_7d)
    agg_30d = _aggregate_window(articles_30d)
    agg_90d = _aggregate_window(articles_90d)

    diffs = [
        _compare_windows(agg_24h, agg_7d, "7d vs 24h"),
        _compare_windows(agg_24h, agg_30d, "30d vs 24h"),
        _compare_windows(agg_24h, agg_90d, "90d vs 24h"),
    ]

    return {
        "aggregates": {
            "24h": agg_24h,
            "7d": agg_7d,
            "30d": agg_30d,
            "90d": agg_90d,
        },
        "diffs": diffs,
    }


def build_geo_24h(articles_24h: list[dict]) -> dict:
    """
    Build geo breakdown for the last 24h per region.

    Returns:
        {
            "Świat": [article, ...],
            "Europa": [...],
            "Polska": [...],
            ...
        }
    """
    geo: dict[str, list] = {}
    for art in articles_24h:
        region = art.get("region", "Świat")
        geo.setdefault(region, []).append(art)
    # Sort each region by published_at desc
    for region in geo:
        geo[region].sort(
            key=lambda a: a.get("published_at", ""), reverse=True)
    return geo
