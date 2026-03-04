from datetime import datetime, timedelta
import logging
import threading
from modules.http_client import safe_get

logger = logging.getLogger(__name__)

FLAG_MAP = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "CHF": "🇨🇭", "AUD": "🇦🇺", "CAD": "🇨🇦", "CNY": "🇨🇳",
    "NZD": "🇳🇿", "PLN": "🇵🇱", "NOK": "🇳🇴", "SEK": "🇸🇪",
    "SGD": "🇸🇬", "HKD": "🇭🇰", "KRW": "🇰🇷",
}

# Finnhub uses 2-letter country codes; map to currency for flag lookup
_COUNTRY_TO_CURRENCY = {
    "US": "USD", "EU": "EUR", "GB": "GBP", "JP": "JPY",
    "CH": "CHF", "AU": "AUD", "CA": "CAD", "CN": "CNY",
    "NZ": "NZD", "PL": "PLN", "NO": "NOK", "SE": "SEK",
    "SG": "SGD", "HK": "HKD", "KR": "KRW",
}

IMPACT_PL = {
    "High":    ("🔴", "Wysoki"),
    "Medium":  ("🟡", "Średni"),
    "Low":     ("⚪", "Niski"),
    "Holiday": ("📅", "Święto"),
}

# Finnhub uses "high"/"medium"/"low" (lowercase) — normalize
_IMPACT_NORMALIZE = {
    "high": "High", "medium": "Medium", "low": "Low",
    "1": "Low", "2": "Medium", "3": "High",
}

# ── Significance mapping for macroeconomic events ──
_EVENT_SIGNIFICANCE = {
    # Inflation & Prices
    "cpi": "Inflacja konsumencka - wzrost = presja na podwyżki stóp",
    "consumer price": "Inflacja konsumencka - wzrost = presja na podwyżki stóp",
    "ppi": "Inflacja producencka - wyprzedza CPI, sygnał trendu cen",
    "producer price": "Inflacja producencka - wyprzedza CPI, sygnał trendu cen",
    "pce price": "Preferowany wskaźnik inflacji Fed - kluczowy dla stóp",
    "core pce": "Inflacja bazowa PCE - główna miara Fed",
    "core inflation": "Inflacja bazowa - trend bez żywności i energii",
    "inflation rate": "Tempo wzrostu cen - determinuje politykę monetarną",
    # Employment
    "non-farm": "Zatrudnienie pozarolnicze - kluczowy wskaźnik rynku pracy USA",
    "nonfarm": "Zatrudnienie pozarolnicze - kluczowy wskaźnik rynku pracy USA",
    "unemployment": "Stopa bezrobocia - wpływa na politykę monetarną",
    "jobless claims": "Nowe wnioski o zasiłek - bieżący sygnał rynku pracy",
    "initial claims": "Wnioski o zasiłek - cotygodniowy barometr zatrudnienia",
    "continuing claims": "Kontynuacja zasiłków - trwałość bezrobocia",
    "employment change": "Zmiana zatrudnienia - siła rynku pracy",
    "adp": "Prywatne zatrudnienie ADP - zapowiedź danych NFP",
    "average hourly earnings": "Wzrost płac - presja inflacyjna z rynku pracy",
    "labor market": "Rynek pracy - kluczowy dla decyzji o stopach",
    # GDP & Growth
    "gdp": "Produkt Krajowy Brutto - miara wzrostu gospodarczego",
    "gross domestic": "PKB - ogólna kondycja gospodarki",
    # Central Banks
    "interest rate": "Decyzja o stopach % - kluczowa dla wszystkich rynków",
    "federal funds": "Stopa Fed - wpływa na globalną płynność",
    "fomc": "Posiedzenie Fed - decyzje o stopach i bilansie",
    "fed chair": "Wystąpienie szefa Fed - wskazówki o przyszłej polityce",
    "fed vice": "Wystąpienie wiceszefa Fed - sygnały polityki",
    "ecb": "Europejski Bank Centralny - stopy i polityka strefy euro",
    "boe": "Bank Anglii - stopy procentowe i polityka UK",
    "boj": "Bank Japonii - polityka monetarna Japonii",
    "rba": "Bank Australii - stopy procentowe AUD",
    "rbnz": "Bank Nowej Zelandii - stopy procentowe NZD",
    "snb": "Bank Szwajcarii - stopy procentowe CHF",
    "boc": "Bank Kanady - stopy procentowe CAD",
    "monetary policy": "Polityka monetarna - kierunek stóp i płynności",
    "rate decision": "Decyzja o stopach - wpływ na waluty i obligacje",
    "press conference": "Konferencja prasowa - wskazówki forward guidance",
    "meeting minutes": "Protokół z posiedzenia - szczegóły dyskusji banku",
    "mpc minutes": "Protokół komitetu monetarnego - intencje polityki",
    # PMI & Business
    "manufacturing pmi": "PMI przemysłu - kondycja sektora wytwórczego",
    "services pmi": "PMI usług - kondycja sektora usługowego",
    "composite pmi": "PMI kompozytowy - ogólna kondycja gospodarki",
    "flash pmi": "Wstępny PMI - wczesny sygnał aktywności",
    "pmi": "Indeks menedżerów - powyżej 50 = ekspansja",
    "ism manufacturing": "ISM przemysł USA - kluczowy wskaźnik aktywności",
    "ism services": "ISM usługi USA - dominujący sektor gospodarki",
    "ism non-manufacturing": "ISM usługi USA - kondycja sektora usługowego",
    # Consumer
    "retail sales": "Sprzedaż detaliczna - barometr popytu konsumenckiego",
    "consumer confidence": "Zaufanie konsumentów - prognoza wydatków",
    "consumer sentiment": "Nastroje konsumentów - prognoza konsumpcji",
    "michigan": "Indeks Michigan - nastroje i oczekiwania konsumentów USA",
    "personal spending": "Wydatki osobiste - siła konsumpcji",
    "personal income": "Dochody osobiste - zdolność do wydatków",
    # Trade & Balance
    "trade balance": "Bilans handlowy - wpływ na kurs waluty",
    "current account": "Rachunek bieżący - przepływy kapitałowe",
    "imports": "Import - popyt wewnętrzny i bilans handlowy",
    "exports": "Eksport - konkurencyjność i popyt zewnętrzny",
    # Housing
    "housing starts": "Rozpoczęcia budów - przyszła aktywność budowlana",
    "building permits": "Pozwolenia budowlane - wyprzedzający wskaźnik",
    "existing home": "Sprzedaż domów - kondycja rynku nieruchomości",
    "new home": "Sprzedaż nowych domów - aktywność budowlana",
    "pending home": "Oczekujące sprzedaże domów - przyszły popyt",
    "home price": "Ceny domów - bogactwo gospodarstw domowych",
    "housing": "Rynek nieruchomości - barometr kondycji gospodarki",
    # Industrial
    "industrial production": "Produkcja przemysłowa - aktywność wytwórcza",
    "capacity utilization": "Wykorzystanie mocy - presja inflacyjna",
    "factory orders": "Zamówienia fabryczne - przyszła produkcja",
    "durable goods": "Zamówienia trwałe - inwestycje biznesowe",
    # Debt & Bonds
    "bond auction": "Aukcja obligacji - popyt na dług rządowy",
    "treasury": "Obligacje skarbowe - barometr stóp i ryzyka",
    "10-year": "Rentowność 10-letnich obligacji - benchmark rynku",
    "30-year": "Rentowność 30-letnich obligacji - długoterminowe stopy",
    "2-year": "Rentowność 2-letnich obligacji - oczekiwania stóp",
    "yield": "Rentowność obligacji - koszt kapitału",
    # Energy & Commodities
    "crude oil": "Zapasy ropy - wpływ na ceny energii",
    "oil inventories": "Zapasy ropy - wpływ na ceny energii",
    "natural gas": "Zapasy gazu - ceny energii",
    "baker hughes": "Aktywne wiertnie - przyszła podaż ropy",
    "eia": "Raport EIA - zapasy surowców energetycznych",
    "opec": "OPEC - decyzje o wydobyciu wpływają na cenę ropy",
    # Surveys & Indices
    "zew": "Indeks ZEW - nastroje inwestorów (Niemcy)",
    "ifo": "Indeks Ifo - klimat biznesowy (Niemcy)",
    "gfk": "GfK - nastroje konsumentów (Niemcy)",
    "tankan": "Tankan - nastroje biznesu (Japonia)",
    "caixin": "Caixin PMI - aktywność sektora prywatnego (Chiny)",
    "ivey": "Ivey PMI - aktywność biznesowa (Kanada)",
    "cb consumer": "Conference Board - zaufanie konsumentów USA",
    "richmond fed": "Richmond Fed - aktywność w regionie",
    "philly fed": "Philadelphia Fed - aktywność przemysłowa regionu",
    "dallas fed": "Dallas Fed - aktywność w regionie",
    "empire state": "Empire State - aktywność przemysłowa NY",
    "chicago pmi": "Chicago PMI - aktywność biznesowa regionu",
    "beige book": "Beige Book Fed - regionalna kondycja gospodarcza",
    # Speeches
    "speaks": "Wystąpienie bankiera centralnego - możliwe sygnały polityki",
    "speech": "Przemówienie - potencjalne wskazówki rynkowe",
    "testimony": "Zeznanie przed komisją - stanowisko polityczne",
    # Other
    "holiday": "Święto - obniżona płynność rynku",
    "bank holiday": "Święto bankowe - rynki zamknięte",
    "leading indicators": "Wskaźniki wyprzedzające - prognoza koniunktury",
    "business confidence": "Zaufanie biznesu - perspektywy inwestycji",
    "wage": "Dane o płacach - presja inflacyjna i konsumpcja",
}


def get_event_significance(event_title):
    """Generate significance description based on event title keywords."""
    title_lower = event_title.lower()
    for keyword, significance in _EVENT_SIGNIFICANCE.items():
        if keyword in title_lower:
            return significance
    return "Dane makroekonomiczne"


# ── Finnhub economic calendar ──

_calendar_cache = {"events": [], "ts": None}
_calendar_cache_lock = threading.Lock()
_CALENDAR_CACHE_TTL = 600  # 10 minutes


def _parse_finnhub_json(data):
    """Parse Finnhub economic calendar JSON into event dicts."""
    events = []
    raw_events = data.get("economicCalendar", data) if isinstance(data, dict) else data
    if isinstance(raw_events, dict):
        raw_events = raw_events.get("result", raw_events.get("economicCalendar", []))
    if not isinstance(raw_events, list):
        return events

    for e in raw_events:
        # Finnhub time field: "2026-03-04 13:30:00" or ISO format
        time_str = e.get("time", "")
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            date_fmt = dt.strftime("%Y-%m-%d")
            time_fmt = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            # Try splitting date-only
            date_fmt = time_str[:10] if len(time_str) >= 10 else "?"
            time_fmt = time_str[11:16] if len(time_str) >= 16 else ""

        country = e.get("country", "")
        currency = _COUNTRY_TO_CURRENCY.get(country, country)

        impact_raw_val = str(e.get("impact", "Low")).strip()
        impact_raw = _IMPACT_NORMALIZE.get(impact_raw_val.lower(), impact_raw_val)
        if impact_raw not in IMPACT_PL:
            impact_raw = "Low"
        icon, label = IMPACT_PL[impact_raw]

        title = e.get("event", "")

        # Format values — Finnhub returns numeric or empty
        def _fmt_val(val):
            if val is None:
                return ""
            if isinstance(val, (int, float)):
                return f"{val:g}"
            return str(val)

        events.append({
            "date":         date_fmt,
            "time":         time_fmt,
            "flag":         FLAG_MAP.get(currency, "🌐"),
            "country":      country,
            "event":        title,
            "impact_icon":  icon,
            "impact_label": label,
            "impact_raw":   impact_raw,
            "forecast":     _fmt_val(e.get("estimate")),
            "previous":     _fmt_val(e.get("prev")),
            "significance": get_event_significance(title),
        })
    return events


def _fetch_finnhub(api_key, from_date, to_date):
    """Fetch economic calendar from Finnhub API.

    Returns: (events_list, error_str_or_None)
    """
    url = (
        f"https://finnhub.io/api/v1/calendar/economic"
        f"?from={from_date}&to={to_date}&token={api_key}"
    )
    try:
        r = safe_get(url, timeout=(8, 15))
        r.raise_for_status()
        data = r.json()
        return _parse_finnhub_json(data), None
    except Exception as exc:
        logger.warning("Finnhub calendar fetch failed: %s", exc)
        return [], str(exc)


def fetch_calendar(api_key=""):
    """Fetch economic calendar: today + 7 days ahead.

    api_key: Finnhub API key (required).
    Returns: (events_list, error_str_or_None)
    Each event dict has keys:
        date, time, flag, country, event, impact_icon, impact_label,
        impact_raw, forecast, previous, significance
    """
    if not api_key:
        return [], "Brak klucza Finnhub API — ustaw w Ustawieniach lub FINNHUB_API_KEY"

    now = datetime.now().timestamp()
    with _calendar_cache_lock:
        if (_calendar_cache["ts"] is not None
                and now - _calendar_cache["ts"] < _CALENDAR_CACHE_TTL
                and _calendar_cache["events"]):
            return list(_calendar_cache["events"]), None

    today = datetime.now().date()
    from_date = today.strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    events, err = _fetch_finnhub(api_key, from_date, to_date)
    if err and not events:
        return [], err

    events.sort(key=lambda x: (x["date"], x["time"]))

    # Deduplicate by (date, time, event, country)
    seen = set()
    unique = []
    for e in events:
        key = (e["date"], e["time"], e["event"], e["country"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    with _calendar_cache_lock:
        _calendar_cache["events"] = unique
        _calendar_cache["ts"] = datetime.now().timestamp()

    return unique, None
