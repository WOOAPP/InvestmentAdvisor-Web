from datetime import datetime
import logging
from modules.http_client import safe_get

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


def fetch_calendar(week="this"):
    """Fetch economic calendar from ForexFactory JSON feed.

    week: 'this' or 'next'
    Returns: (events_list, error_str_or_None)
    Each event dict has keys:
        date, time, flag, country, event, impact_icon, impact_label,
        impact_raw, forecast, previous, significance
    """
    slug = "thisweek" if week == "this" else "nextweek"
    url = f"https://nfs.faireconomy.media/ff_calendar_{slug}.json"
    try:
        r = safe_get(url)
        data = r.json()
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
        events.sort(key=lambda x: (x["date"], x["time"]))
        return events, None
    except Exception as exc:
        return [], str(exc)
