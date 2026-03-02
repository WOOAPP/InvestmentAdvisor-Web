import anthropic
import openai
from datetime import datetime
from zoneinfo import ZoneInfo
import sys, os

_WARSAW = ZoneInfo("Europe/Warsaw")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_api_key

# ── Provider configuration ────────────────────────────────────────
_PROVIDER_DEFAULTS = {
    "anthropic":   {"key": "anthropic",   "model": "claude-opus-4-6",
                    "env": "ANTHROPIC_API_KEY"},
    "openai":      {"key": "openai",      "model": "gpt-4o",
                    "env": "OPENAI_API_KEY"},
    "openrouter":  {"key": "openrouter",  "model": "openai/gpt-4o",
                    "env": "OPENROUTER_API_KEY",
                    "base_url": "https://openrouter.ai/api/v1"},
}


# ── Unified provider call ─────────────────────────────────────────
def _call_provider(provider, api_key, model, system_prompt,
                   messages, max_tokens=4096):
    """Call Anthropic or OpenAI-compatible API. Returns (text, usage)."""
    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=system_prompt, messages=messages)
        return response.content[0].text, getattr(response, "usage", None)
    else:
        kwargs = {"api_key": api_key}
        base_url = _PROVIDER_DEFAULTS.get(provider, {}).get("base_url")
        if base_url:
            kwargs["base_url"] = base_url
        client = openai.OpenAI(**kwargs)
        oai_messages = []
        if system_prompt:
            oai_messages.append({"role": "system", "content": system_prompt})
        oai_messages.extend(messages)
        response = client.chat.completions.create(
            model=model, max_tokens=max_tokens, messages=oai_messages)
        return response.choices[0].message.content, getattr(response, "usage", None)


def _run_provider(config, system_prompt, user_message):
    """Run a single system+user prompt through the configured provider."""
    provider = config.get("ai_provider", "anthropic")
    pcfg = _PROVIDER_DEFAULTS.get(provider)
    if not pcfg:
        return _make_result("Błąd: nieznany dostawca AI. Sprawdź ustawienia.")
    api_key = get_api_key(config, pcfg["key"])
    if not api_key:
        return _make_result(
            f"Brak klucza API {provider.capitalize()}. "
            f"Ustaw {pcfg['env']} lub dodaj klucz w Ustawieniach.")
    model = config.get("ai_model", pcfg["model"])
    try:
        text, usage = _call_provider(
            provider, api_key, model, system_prompt,
            [{"role": "user", "content": user_message}])
        return _make_result(text, usage)
    except Exception as e:
        return _make_result(f"Błąd {provider.capitalize()} API: {e}")


# ── Public API ────────────────────────────────────────────────────
def run_analysis(config, market_summary, news_list, scraped_text="",
                  macro_text=""):
    """Wysyła dane do wybranego modelu AI i zwraca dict z kluczami:
    text, input_tokens, output_tokens."""
    prompt = config.get("prompt", "Przeanalizuj sytuację rynkową.")
    if macro_text:
        full_message = _build_macro_prompt(
            market_summary, macro_text, scraped_text)
    else:
        full_message = _build_legacy_prompt(
            market_summary, news_list, scraped_text)
    return _run_provider(config, prompt, full_message)


def run_chat(config, messages, system_prompt=""):
    """Send a multi-turn chat conversation to the configured chat model.

    Always returns a plain string (backward-compatible).
    """
    provider = config.get("chat_provider") or config.get("ai_provider", "anthropic")
    model = config.get("chat_model") or config.get("ai_model", "claude-sonnet-4-6")

    pcfg = _PROVIDER_DEFAULTS.get(provider)
    if not pcfg:
        return "Nieznany dostawca AI dla czatu."

    api_key = get_api_key(config, pcfg["key"])
    if not api_key:
        return (f"Brak klucza API {provider.capitalize()}. "
                f"Ustaw {pcfg['env']} lub dodaj klucz w Ustawieniach.")
    try:
        text, _ = _call_provider(
            provider, api_key, model, system_prompt,
            messages, max_tokens=2048)
        return text
    except Exception as e:
        return f"Błąd {provider.capitalize()}: {e}"


def generate_instrument_profile(config, symbol, name, category):
    """Generate a one-time AI profile for an instrument (cached by caller)."""
    system = (
        "Jesteś ekspertem rynków finansowych. Przygotuj zwięzły profil "
        "instrumentu finansowego. Odpowiadaj po polsku, konkretnie i rzeczowo."
    )
    custom_prompt = config.get("profile_prompt", "").strip()
    if not custom_prompt:
        custom_prompt = (
            "Opisz ten instrument w trzech sekcjach:\n\n"
            "## 1. Czym jest\n"
            "Krótki opis instrumentu w kontekście jego kategorii.\n\n"
            "## 2. Co wpływa na kurs\n"
            "Najważniejsze czynniki wpływające na wahania ceny "
            "(makro, geopolityka, sezonowość, korelacje).\n\n"
            "## 3. Na co wpływa\n"
            "Gdzie jest \"transmisja\" na inne rynki, branże, instrumenty.\n\n"
            "Bądź zwięzły (max 300 słów łącznie). Używaj konkretnych przykładów."
        )
    user_msg = (
        f"Instrument: {name} ({symbol})\n"
        f"Kategoria: {category}\n\n"
        f"{custom_prompt}"
    )
    return _result_text(_run_provider(config, system, user_msg))


def get_available_models(provider):
    """Zwraca listę dostępnych modeli dla danego dostawcy."""
    models = {
        "anthropic": [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001"
        ],
        "openai": [
            "gpt-5.2",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "o1",
            "o1-mini",
            "o1-preview",
            "o3-mini",
        ],
        "openrouter": [
            "anthropic/claude-sonnet-4",
            "anthropic/claude-haiku-4",
            "openai/gpt-5.2",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "google/gemini-2.0-flash-001",
            "google/gemini-2.5-pro-preview",
            "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-chat-v3-0324",
            "mistralai/mistral-large-latest",
        ]
    }
    return models.get(provider, [])


# ── Helpers ───────────────────────────────────────────────────────
def _make_result(text, usage=None):
    """Wrap API response text and optional usage into a standard dict."""
    inp = 0
    out = 0
    if usage is not None:
        inp = getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0
        out = getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0
    return {"text": text, "input_tokens": int(inp), "output_tokens": int(out)}


def _result_text(result):
    """Extract plain text from a result (dict or str)."""
    if isinstance(result, dict):
        return result.get("text", "")
    return result


def _build_macro_prompt(market_summary, macro_text, scraped_text=""):
    """Build the new structured prompt with macro-trend data."""
    parts = [
        f"Data analizy: {datetime.now(_WARSAW).strftime('%Y-%m-%d %H:%M')}",
        "",
        market_summary,
        "",
        macro_text,
    ]
    if scraped_text:
        parts.append("")
        parts.append("=== TREŚĆ ZE ŹRÓDEŁ WWW ===")
        parts.append(scraped_text)
    parts.append("")
    parts.append(
        "Na podstawie powyższych danych przeprowadź analizę w następującej strukturze:\n"
        "0) NEWS DNIA — omów najważniejszy news i jego implikacje\n"
        "1) GEO 24H — sytuacja per region (Świat/Europa/Polska/Am.Płn./Azja/Australia)\n"
        "2) PORÓWNANIE TRENDU: 24h vs 7d vs 30d vs 90d — kontynuacje, anomalie, punkty zwrotne\n"
        "3) IMPLIKACJE DLA INSTRUMENTÓW — jak powyższe wpływa na poszczególne aktywa ze snapshotu\n"
        "4) SCENARIUSZE + RYZYKO (skala 1–10) — scenariusz bazowy, optymistyczny, pesymistyczny\n"
        "5) PERSPEKTYWA RUCHU — kierunki, ale NIE porada inwestycyjna\n"
        "\nOdpowiadaj po polsku. Bądź konkretny i rzeczowy."
    )
    return "\n".join(parts)


def _build_legacy_prompt(market_summary, news_list, scraped_text=""):
    """Legacy prompt builder for backward compatibility."""
    news_text = ""
    if news_list and not any("error" in n for n in news_list):
        news_text = "\n=== AKTUALNE WIADOMOŚCI ===\n"
        for i, n in enumerate(news_list[:8], 1):
            news_text += f"{i}. [{n.get('source','')}] {n.get('title','')}\n"
            if n.get("description"):
                news_text += f"   {n.get('description','')[:150]}...\n"

    return (
        f"Data analizy: {datetime.now(_WARSAW).strftime('%Y-%m-%d %H:%M')}\n\n"
        f"{market_summary}\n"
        f"{news_text}\n"
        f"{'=== TREŚĆ ZE ŹRÓDEŁ WWW ===' + chr(10) + scraped_text if scraped_text else ''}\n\n"
        f"Na podstawie powyższych danych przeprowadź szczegółową analizę."
    )
