import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def scrape_url(url, max_chars=3000):
    """Pobiera pełną treść tekstową ze strony."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Usuń zbędne elementy
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "button", "iframe", "img"]):
            tag.decompose()

        # Spróbuj znaleźć główną treść artykułu
        content = None
        for selector in ["article", "main", ".article-body", ".content",
                          ".post-content", "#content", ".entry-content"]:
            el = soup.select_one(selector)
            if el:
                content = el.get_text(separator="\n", strip=True)
                break

        if not content:
            content = soup.get_text(separator="\n", strip=True)

        # Wyczyść puste linie
        lines = [l.strip() for l in content.split("\n") if len(l.strip()) > 40]
        text = "\n".join(lines)
        return text[:max_chars]

    except Exception as e:
        return f"[Błąd pobierania {url}: {e}]"

def scrape_all(urls, max_chars_per_site=2000):
    """Pobiera treść ze wszystkich podanych URL-i."""
    if not urls:
        return ""
    results = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        text = scrape_url(url, max_chars=max_chars_per_site)
        results.append(f"=== ŹRÓDŁO: {url} ===\n{text}\n")
    return "\n".join(results)