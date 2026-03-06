from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
import threading
from modules.http_client import safe_get

_WARSAW = ZoneInfo("Europe/Warsaw")

logger = logging.getLogger(__name__)

FLAG_MAP = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "CHF": "🇨🇭", "AUD": "🇦🇺", "CAD": "🇨🇦", "CNY": "🇨🇳",
    "NZD": "🇳🇿", "PLN": "🇵🇱", "NOK": "🇳🇴", "SEK": "🇸🇪",
    "SGD": "🇸🇬", "HKD": "🇭🇰", "KRW": "🇰🇷",
}

IMPACT_PL = {
    "High":    ("🔴", "Wysoki"),
    "Medium":  ("🟡", "Średni"),
    "Low":     ("⚪", "Niski"),
    "Holiday": ("📅", "Święto"),
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


def _parse_ff_json(data):
    """Parse ForexFactory JSON into event dicts."""
    events = []
    for e in data:
        date_str = e.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str)
            date_fmt = dt.strftime("%Y-%m-%d")
            time_fmt = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            date_fmt = date_str[:10] if date_str else "?"
            time_fmt = ""

        country = e.get("country", "")
        impact_raw = e.get("impact", "Low")
        icon, label = IMPACT_PL.get(impact_raw, ("⚪", impact_raw))
        title = e.get("title", "")
        events.append({
            "date":         date_fmt,
            "time":         time_fmt,
            "flag":         FLAG_MAP.get(country, "🌐"),
            "country":      country,
            "event":        title,
            "impact_icon":  icon,
            "impact_label": label,
            "impact_raw":   impact_raw,
            "forecast":     e.get("forecast", "") or "",
            "previous":     e.get("previous", "") or "",
            "significance": get_event_significance(title),
        })
    return events


_calendar_cache = {"events": [], "ts": None}
_calendar_cache_lock = threading.Lock()
_CALENDAR_CACHE_TTL = 3600  # 1 hour — ForexFactory limits to 2 req / 5 min


def _fetch_thisweek():
    """Fetch current week from ForexFactory.

    Returns: (events_list, error_str_or_None)
    """
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    try:
        r = safe_get(url, timeout=(8, 15))
        r.raise_for_status()
        data = r.json()
        return _parse_ff_json(data), None
    except Exception as exc:
        logger.warning("Calendar fetch failed: %s", exc)
        return [], str(exc)


def _fetch_nextweek():
    """Fetch next week from ForexFactory.

    Returns: (events_list, error_str_or_None)
    """
    url = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"
    try:
        r = safe_get(url, timeout=(8, 15))
        r.raise_for_status()
        data = r.json()
        return _parse_ff_json(data), None
    except Exception as exc:
        logger.warning("Calendar nextweek fetch failed: %s", exc)
        return [], str(exc)


_calendar_14d_cache: dict = {"events": [], "ts": None}
_calendar_14d_lock = threading.Lock()


def fetch_calendar_14d():
    """Fetch economic calendar for today + next 14 days (thisweek + nextweek).

    Returns: (events_list, error_str_or_None)
    Each event dict has keys:
        date, time, flag, country, event, impact_icon, impact_label,
        impact_raw, forecast, previous, significance
    """
    now = datetime.now(_WARSAW).timestamp()
    with _calendar_14d_lock:
        if (_calendar_14d_cache["ts"] is not None
                and now - _calendar_14d_cache["ts"] < _CALENDAR_CACHE_TTL
                and _calendar_14d_cache["events"]):
            cached = list(_calendar_14d_cache["events"])
            cutoff = (datetime.now(_WARSAW).date() + timedelta(days=14)).strftime("%Y-%m-%d")
            today_str = datetime.now(_WARSAW).date().strftime("%Y-%m-%d")
            return [e for e in cached if today_str <= e["date"] <= cutoff], None

    this_events, this_err = _fetch_thisweek()
    next_events, next_err = _fetch_nextweek()

    all_events = this_events + next_events
    if not all_events:
        return [], this_err or next_err

    # Deduplicate by (date, time, event, country)
    seen = set()
    unique = []
    for e in all_events:
        key = (e["date"], e["time"], e["event"], e["country"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    unique.sort(key=lambda x: (x["date"], x["time"]))

    with _calendar_14d_lock:
        _calendar_14d_cache["events"] = unique
        _calendar_14d_cache["ts"] = datetime.now(_WARSAW).timestamp()

    today_str = datetime.now(_WARSAW).date().strftime("%Y-%m-%d")
    cutoff = (datetime.now(_WARSAW).date() + timedelta(days=14)).strftime("%Y-%m-%d")
    return [e for e in unique if today_str <= e["date"] <= cutoff], None


def format_calendar_for_ai(events, days=7):
    """Format calendar events into a compact text block for AI context.

    Filters to the next `days` days, High+Medium impact only.
    Returns a ready-to-inject string (empty string if no relevant events).
    """
    if not events:
        return ""
    from datetime import timedelta
    today = datetime.now(_WARSAW).date()
    today_str = today.strftime("%Y-%m-%d")
    cutoff_str = (today + timedelta(days=days)).strftime("%Y-%m-%d")

    filtered = [
        e for e in events
        if today_str <= e.get("date", "") <= cutoff_str
        and e.get("impact_raw", "") in ("High", "Medium")
    ]
    if not filtered:
        return ""

    lines = [f"=== KALENDARZ MAKROEKONOMICZNY (najbliższe {days} dni, wpływ Wysoki/Średni) ==="]
    current_date = None
    for e in filtered:
        if e["date"] != current_date:
            current_date = e["date"]
            lines.append(f"\n{e['date']}:")
        impact_str = f"{e.get('impact_icon', '')} {e.get('impact_label', '')}".strip()
        parts = [f"  {e.get('time', ''):5}  {e.get('flag', '')} {e.get('country', ''):4}  [{impact_str}]  {e.get('event', '')}"]
        if e.get("forecast"):
            parts[0] += f"  Prognoza: {e['forecast']}"
        if e.get("previous"):
            parts[0] += f"  Poprz: {e['previous']}"
        lines.append(parts[0])
        sig = e.get("significance", "")
        if sig and sig != "Dane makroekonomiczne":
            lines.append(f"         → {sig}")
    return "\n".join(lines)


def fetch_calendar():
    """Fetch economic calendar — events from today to end of week.

    Uses ForexFactory thisweek endpoint with aggressive caching (1h TTL).
    Returns: (events_list, error_str_or_None)
    Each event dict has keys:
        date, time, flag, country, event, impact_icon, impact_label,
        impact_raw, forecast, previous, significance
    """
    now = datetime.now(_WARSAW).timestamp()
    with _calendar_cache_lock:
        if (_calendar_cache["ts"] is not None
                and now - _calendar_cache["ts"] < _CALENDAR_CACHE_TTL
                and _calendar_cache["events"]):
            cached = list(_calendar_cache["events"])
            today_str = datetime.now(_WARSAW).date().strftime("%Y-%m-%d")
            return [e for e in cached if e["date"] >= today_str], None

    events, err = _fetch_thisweek()
    if err and not events:
        return [], err

    # Deduplicate by (date, time, event, country)
    seen = set()
    unique = []
    for e in events:
        key = (e["date"], e["time"], e["event"], e["country"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    unique.sort(key=lambda x: (x["date"], x["time"]))

    with _calendar_cache_lock:
        _calendar_cache["events"] = unique
        _calendar_cache["ts"] = datetime.now(_WARSAW).timestamp()

    # Filter from today onward
    today_str = datetime.now(_WARSAW).date().strftime("%Y-%m-%d")
    return [e for e in unique if e["date"] >= today_str], None
