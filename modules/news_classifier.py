"""
C3: Deterministic region and topic classification for news articles.

No ML — pure keyword/regex dictionaries.  Transparent and auditable.
"""

import re

# ── Region classification ───────────────────────────────────────────
# Order matters: more specific patterns first.
# Each tuple: (region_name, compiled_regex_patterns_for_title+description)

_REGION_RULES: list[tuple[str, re.Pattern]] = [
    # Polska
    ("Polska", re.compile(
        r"\b(poland|polish|polska|warszaw|gpw|wig\d*|nbp|pln|zloty|złot"
        r"|tusk|morawiecki|kaczyński|sejm|senat|orlen|kghm|pekao"
        r"|pko\s?bp|allegro\.pl|biedronka|żabka|gdańsk|kraków|wrocław"
        r"|łódź|poznań|katowice)\b", re.IGNORECASE)),

    # Europa (bez Polska — Polska ma priorytet)
    ("Europa", re.compile(
        r"\b(europ\w*|eu\b|euro\s?zone|eurozone|ecb|lagarde|euro\b"
        r"|german\w*|france|french|italy|italian|spain|spanish|dutch|netherlands"
        r"|belgium|austria\w*|switzerland|swiss|sweden|norway|denmark|finland"
        r"|portugal|greece|ireland|czech|hungar\w*|romania|bulgaria|croatia"
        r"|brexit|uk\b|britain|british|london|paris|berlin|frankfurt|dax\b"
        r"|stoxx|ftse|cac\s?40|bund|gilt|boe\b|bank\s?of\s?england"
        r"|bundesbank|nato\b)\b", re.IGNORECASE)),

    # Ameryka Północna
    ("Ameryka Pn.", re.compile(
        r"\b(usa|u\.s\.|united\s?states|america|washington|wall\s?street"
        r"|fed\b|federal\s?reserve|powell|yellen|treasury|congress|senate"
        r"|s&p\s?500|nasdaq|dow\s?jones|nyse|spy\b|qqq\b"
        r"|silicon\s?valley|california|texas|new\s?york|chicago"
        r"|canada|canadian|toronto|tsx|mexico|mexican|peso"
        r"|trump|biden|white\s?house)\b", re.IGNORECASE)),

    # Azja
    ("Azja", re.compile(
        r"\b(china|chinese|beijing|shanghai|hong\s?kong|taiwan|taipei"
        r"|japan|japanese|tokyo|nikkei|boj\b|yen\b|abe\b"
        r"|korea|korean|seoul|kospi|samsung"
        r"|india|indian|mumbai|sensex|nifty|rupee|modi\b"
        r"|asean|singapore|indonesia|vietnam|thailand|malaysia|philippines"
        r"|asia|asian)\b", re.IGNORECASE)),

    # Australia / Oceania
    ("Australia", re.compile(
        r"\b(australia|australian|sydney|asx\b|rba\b|aud\b"
        r"|new\s?zealand|nzd\b|rbnz)\b", re.IGNORECASE)),
]

# Fallback
_DEFAULT_REGION = "Świat"


def classify_region(title: str, description: str = "") -> str:
    """Return region name based on keyword rules. First match wins."""
    text = f"{title} {description}"
    for region, pattern in _REGION_RULES:
        if pattern.search(text):
            return region
    return _DEFAULT_REGION


# ── Topic classification ────────────────────────────────────────────

_TOPIC_RULES: list[tuple[str, re.Pattern]] = [
    ("banki centralne", re.compile(
        r"\b(central\s?bank|fed\b|federal\s?reserve|ecb|boe|boj|rba|rbnz|nbp"
        r"|pboc|rate\s?decision|interest\s?rate|stopy\s?proc|monetary\s?policy"
        r"|quantitative|tapering|hawkish|dovish|powell|lagarde|ueda)\b",
        re.IGNORECASE)),

    ("inflacja/stopy", re.compile(
        r"\b(inflat|cpi\b|pce\b|deflat|price\s?index|consumer\s?price"
        r"|core\s?inflation|disinflat|stagflat|hyperinflat"
        r"|yield|bond\s?yield|treasury\s?yield|bund\s?yield)\b",
        re.IGNORECASE)),

    ("rynek pracy", re.compile(
        r"\b(employ|unemploy|jobless|payroll|non.?farm|labor|labour"
        r"|hiring|layoff|job\s?market|workforce|wage|salary|zatrudnieni"
        r"|bezroboci|rynek\s?pracy)\b", re.IGNORECASE)),

    ("energia", re.compile(
        r"\b(oil\b|crude|brent|wti|opec|natural\s?gas|lng\b|petroleum"
        r"|energy\s?crisis|energy\s?price|solar|wind\s?power|nuclear"
        r"|coal\b|ropa\b|gaz\b|energia)\b", re.IGNORECASE)),

    ("handel", re.compile(
        r"\b(trade\s?war|tariff\w*|sanction\w*|embargo\w*|import\s?dut\w*|export\s?ban"
        r"|trade\s?deal|trade\s?deficit|trade\s?surplus|wto\b|nafta\b|usmca"
        r"|supply\s?chain|shipping|port\b|freight|handel|cło|cła)\b",
        re.IGNORECASE)),

    ("konflikt", re.compile(
        r"\b(war\b|conflict|military|invasion|attack|missile|drone\s?strike"
        r"|geopoliti|tension|escalat|cease.?fire|peace\s?talk|nato"
        r"|nuclear\s?threat|sanction|ukrain|russia|gaza|israel|iran"
        r"|north\s?korea|wojna|konflikt)\b", re.IGNORECASE)),

    ("tech/AI", re.compile(
        r"\b(ai\b|artificial\s?intelligen|machine\s?learn|deep\s?learn"
        r"|chatgpt|openai|google\s?ai|nvidia|semiconductor|chip\b|chips\b"
        r"|tech\s?stock|big\s?tech|apple|microsoft|amazon|alphabet|meta"
        r"|tesla|startup|fintech|blockchain|quantum\s?comput"
        r"|sztuczn|technologi)\b", re.IGNORECASE)),

    ("makro", re.compile(
        r"\b(gdp\b|pkb\b|pmi\b|recession|growth|economic\s?growth"
        r"|fiscal|budget|debt\s?ceiling|sovereign\s?debt|deficit"
        r"|stimulus|spending|austerity|imf\b|world\s?bank"
        r"|wzrost|recesja|produkcja\s?przemysłowa)\b", re.IGNORECASE)),

    ("nieruchomości", re.compile(
        r"\b(real\s?estate|housing|mortgage|property|home\s?price"
        r"|rent\b|construction|nieruchomości|mieszkani)\b",
        re.IGNORECASE)),

    ("krypto", re.compile(
        r"\b(bitcoin|btc\b|ethereum|eth\b|crypto|defi|nft\b"
        r"|stablecoin|binance|coinbase|token|halving|kryptowalut)\b",
        re.IGNORECASE)),

    ("surowce", re.compile(
        r"\b(gold\b|silver\b|copper|platinum|palladium|iron\s?ore"
        r"|wheat|corn\b|soybean|coffee|cocoa|sugar|commodity|commodities"
        r"|złoto|srebro|miedź|surowc)\b", re.IGNORECASE)),
]

_DEFAULT_TOPIC = "inne"


def classify_topic(title: str, description: str = "") -> str:
    """Return topic name based on keyword rules. First match wins."""
    text = f"{title} {description}"
    for topic, pattern in _TOPIC_RULES:
        if pattern.search(text):
            return topic
    return _DEFAULT_TOPIC


def classify_article(article: dict) -> dict:
    """Add region and topic fields to an article dict (in-place + return)."""
    title = article.get("title", "")
    desc = article.get("description", "")
    article["region"] = classify_region(title, desc)
    article["topic"] = classify_topic(title, desc)
    return article


def classify_articles(articles: list[dict]) -> list[dict]:
    """Classify region & topic for a list of articles."""
    for art in articles:
        classify_article(art)
    return articles
