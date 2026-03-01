import requests
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

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


def fetch_calendar(week="this"):
    """Fetch economic calendar from ForexFactory JSON feed.

    week: 'this' or 'next'
    Returns: (events_list, error_str_or_None)
    Each event dict has keys:
        date, time, flag, country, event, impact_icon, impact_label,
        impact_raw, forecast, previous
    """
    slug = "thisweek" if week == "this" else "nextweek"
    url = f"https://nfs.faireconomy.media/ff_calendar_{slug}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=14)
        r.raise_for_status()
        data = r.json()
        events = []
        for e in data:
            date_str = e.get("date", "")
            try:
                dt = datetime.fromisoformat(date_str)
                date_fmt = dt.strftime("%Y-%m-%d")
                time_fmt = dt.strftime("%H:%M")
            except Exception:
                date_fmt = date_str[:10] if date_str else "?"
                time_fmt = ""

            country = e.get("country", "")
            impact_raw = e.get("impact", "Low")
            icon, label = IMPACT_PL.get(impact_raw, ("⚪", impact_raw))
            events.append({
                "date":         date_fmt,
                "time":         time_fmt,
                "flag":         FLAG_MAP.get(country, "🌐"),
                "country":      country,
                "event":        e.get("title", ""),
                "impact_icon":  icon,
                "impact_label": label,
                "impact_raw":   impact_raw,
                "forecast":     e.get("forecast", "") or "",
                "previous":     e.get("previous", "") or "",
            })
        events.sort(key=lambda x: (x["date"], x["time"]))
        return events, None
    except Exception as exc:
        return [], str(exc)
