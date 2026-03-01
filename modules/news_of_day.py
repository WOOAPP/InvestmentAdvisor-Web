"""
C4: "News dnia" — select the single most impactful news from the 24-72h window.

Scoring factors:
  1. Source weight (trusted high-quality sources score higher)
  2. Recency (newer is better, within the 72h window)
  3. High-impact keywords (war, rate decision, crash, etc.)
  4. Topic weight (banki centralne > konflikt > makro > ...)
"""

import re
from datetime import datetime, timedelta

# ── Source weights ──────────────────────────────────────────────────
# Higher = more trusted / impactful.  Range 1-10.
SOURCE_WEIGHTS: dict[str, int] = {
    "reuters": 10,
    "bloomberg": 10,
    "financial times": 9,
    "the wall street journal": 9,
    "associated press": 9,
    "bbc": 8,
    "cnbc": 8,
    "the economist": 8,
    "the guardian": 7,
    "the new york times": 8,
    "al jazeera": 7,
    "bankier.pl": 7,
    "pap": 7,
    "money.pl": 6,
    "investing.com": 6,
    "marketwatch": 7,
    "seeking alpha": 5,
    "business insider": 6,
    "coindesk": 5,
    "zerohedge": 4,
}
_DEFAULT_SOURCE_WEIGHT = 3

# ── High-impact keywords ───────────────────────────────────────────
_HIGH_IMPACT_RE = re.compile(
    r"\b(crash|recession|war\b|invasion|default|collapse|emergency|crisis"
    r"|rate\s?cut|rate\s?hike|rate\s?decision|surprise|shock|black\s?swan"
    r"|bankrupt|bail.?out|sanction|escalat|cease.?fire|nuclear"
    r"|pandemic|shutdown|tariff|trade\s?war|currency\s?crisis"
    r"|record\s?high|record\s?low|flash\s?crash|bank\s?run"
    r"|kryzys|wojna|recesja|krach|upadłość|sankcj)\b",
    re.IGNORECASE,
)

# ── Topic weights ──────────────────────────────────────────────────
TOPIC_WEIGHTS: dict[str, float] = {
    "banki centralne": 3.0,
    "konflikt": 2.5,
    "inflacja/stopy": 2.0,
    "handel": 2.0,
    "makro": 1.8,
    "energia": 1.5,
    "rynek pracy": 1.5,
    "tech/AI": 1.2,
    "krypto": 1.0,
    "surowce": 1.0,
    "nieruchomości": 0.8,
    "inne": 0.5,
}


def _source_score(source_name: str) -> float:
    """Lookup source weight (case-insensitive partial match)."""
    s = source_name.strip().lower()
    for key, weight in SOURCE_WEIGHTS.items():
        if key in s or s in key:
            return float(weight)
    return float(_DEFAULT_SOURCE_WEIGHT)


def _recency_score(published_at: str) -> float:
    """Score 0-10 based on how recent the article is (within 72h)."""
    try:
        # Handle both ISO formats
        pub = published_at.replace("Z", "+00:00")
        if "T" in pub:
            dt = datetime.fromisoformat(pub.replace("+00:00", ""))
        else:
            dt = datetime.strptime(pub[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return 2.0  # unknown date → low score
    age_hours = (datetime.utcnow() - dt).total_seconds() / 3600
    if age_hours < 0:
        age_hours = 0
    # 0h → 10, 72h → 1
    return max(1.0, 10.0 - (age_hours / 72.0) * 9.0)


def _keyword_score(title: str, description: str = "") -> float:
    """Bonus for high-impact keywords.  0 or 3-6 depending on match count."""
    text = f"{title} {description}"
    matches = _HIGH_IMPACT_RE.findall(text)
    if not matches:
        return 0.0
    return min(3.0 + len(matches), 6.0)


def _topic_score(topic: str) -> float:
    return TOPIC_WEIGHTS.get(topic, 0.5)


def score_article(article: dict) -> float:
    """Compute composite score for a single article."""
    src = _source_score(article.get("source", ""))
    rec = _recency_score(article.get("published_at", ""))
    kw = _keyword_score(article.get("title", ""),
                        article.get("description", ""))
    tp = _topic_score(article.get("topic", "inne"))
    # Weighted composite
    return (src * 1.5) + (rec * 1.0) + (kw * 2.0) + (tp * 1.5)


def select_news_of_day(articles: list[dict]) -> dict | None:
    """
    Select the single most impactful news from a list (typically 24-72h).

    Returns a structured object:
        {
            "selected_news": { ... article ... },
            "score": float,
            "justification": [str, ...],        # 3-6 bullet points
            "watch_signals": [str, ...],         # 2-5 signals
        }
    """
    if not articles:
        return None

    scored = []
    for art in articles:
        s = score_article(art)
        scored.append((s, art))
    scored.sort(key=lambda x: x[0], reverse=True)

    best_score, best = scored[0]

    # Build justification
    justification = _build_justification(best, best_score)
    watch = _build_watch_signals(best, articles)

    return {
        "selected_news": best,
        "score": round(best_score, 2),
        "justification": justification,
        "watch_signals": watch,
    }


def _build_justification(article: dict, score: float) -> list[str]:
    """Generate 3-6 justification bullets."""
    bullets = []
    src = article.get("source", "nieznane")
    bullets.append(f"Źródło: {src} (waga: {_source_score(src):.0f}/10)")

    rec = _recency_score(article.get("published_at", ""))
    bullets.append(f"Aktualność: {rec:.1f}/10")

    kw = _keyword_score(article.get("title", ""),
                        article.get("description", ""))
    if kw > 0:
        bullets.append(f"Słowa kluczowe high-impact wykryte (bonus: +{kw:.1f})")
    else:
        bullets.append("Brak słów kluczowych high-impact")

    topic = article.get("topic", "inne")
    bullets.append(f"Temat: {topic} (waga: {_topic_score(topic):.1f})")

    region = article.get("region", "Świat")
    bullets.append(f"Region: {region}")

    bullets.append(f"Łączny scoring: {score:.1f}")
    return bullets[:6]


def _build_watch_signals(selected: dict, all_articles: list[dict]) -> list[str]:
    """Generate 2-5 'co obserwować' signals based on top news context."""
    signals = []
    topic = selected.get("topic", "inne")

    topic_signal_map = {
        "banki centralne": "Decyzje stóp procentowych i forward guidance",
        "konflikt": "Eskalacja/deeskalacja i wpływ na ceny energii",
        "inflacja/stopy": "Odczyty CPI/PPI i reakcja rynku obligacji",
        "handel": "Nowe taryfy celne i retaliacja partnerów handlowych",
        "makro": "Dane PKB i PMI w kolejnych tygodniach",
        "energia": "Decyzje OPEC+ i poziomy zapasów",
        "rynek pracy": "Payrolls i dynamika płac",
        "tech/AI": "Wyniki big tech i regulacje AI",
        "krypto": "Regulacje i przepływy instytucjonalne",
        "surowce": "Popyt z Chin i poziomy zapasów",
    }
    if topic in topic_signal_map:
        signals.append(topic_signal_map[topic])

    # Add region-specific signal
    region = selected.get("region", "Świat")
    region_signals = {
        "Polska": "Decyzje RPP i kurs PLN",
        "Europa": "Dane ze strefy euro i polityka ECB",
        "Ameryka Pn.": "Dane z USA i retoryka Fed",
        "Azja": "Dane z Chin i polityka PBoC",
        "Australia": "Decyzje RBA i eksport surowców",
    }
    if region in region_signals:
        signals.append(region_signals[region])

    # Count how many articles share the same topic → trend signal
    same_topic = sum(1 for a in all_articles if a.get("topic") == topic)
    if same_topic >= 5:
        signals.append(f"Temat '{topic}' dominuje ({same_topic} artykułów) — nasilony trend")
    elif same_topic >= 3:
        signals.append(f"Temat '{topic}' powtarza się ({same_topic} artykułów)")

    # Ensure 2-5
    if len(signals) < 2:
        signals.append("Ogólna zmienność i sentyment rynkowy")
    return signals[:5]
