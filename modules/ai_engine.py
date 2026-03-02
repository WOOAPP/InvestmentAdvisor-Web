import anthropic
import openai
from datetime import datetime
from zoneinfo import ZoneInfo
import sys, os

_WARSAW = ZoneInfo("Europe/Warsaw")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_api_key

def run_analysis(config, market_summary, news_list, scraped_text="",
                  macro_text=""):
    """Wysyła dane do wybranego modelu AI i zwraca dict z kluczami:
    text, input_tokens, output_tokens."""
    provider = config.get("ai_provider", "anthropic")
    prompt = config.get("prompt", "Przeanalizuj sytuację rynkową.")

    # ── Macro-trend payload (new structured data) ────────────
    if macro_text:
        full_message = _build_macro_prompt(
            market_summary, macro_text, scraped_text)
    else:
        # Legacy path (backward compat)
        full_message = _build_legacy_prompt(
            market_summary, news_list, scraped_text)

    if provider == "anthropic":
        return _run_anthropic(config, prompt, full_message)
    elif provider == "openai":
        return _run_openai(config, prompt, full_message)
    elif provider == "openrouter":
        return _run_openrouter(config, prompt, full_message)
    else:
        return _make_result("Błąd: nieznany dostawca AI. Sprawdź ustawienia.")


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


def _run_anthropic(config, system_prompt, user_message):
    api_key = get_api_key(config, "anthropic")
    if not api_key:
        return _make_result("Brak klucza API Anthropic. Ustaw ANTHROPIC_API_KEY lub dodaj klucz w Ustawieniach.")
    try:
        client = anthropic.Anthropic(api_key=api_key)
        model = config.get("ai_model", "claude-opus-4-6")
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return _make_result(response.content[0].text, getattr(response, "usage", None))
    except Exception as e:
        return _make_result(f"Błąd Anthropic API: {str(e)}")

def _run_openai(config, system_prompt, user_message):
    api_key = get_api_key(config, "openai")
    if not api_key:
        return _make_result("Brak klucza API OpenAI. Ustaw OPENAI_API_KEY lub dodaj klucz w Ustawieniach.")
    try:
        client = openai.OpenAI(api_key=api_key)
        model = config.get("ai_model", "gpt-4o")
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        return _make_result(response.choices[0].message.content, getattr(response, "usage", None))
    except Exception as e:
        return _make_result(f"Błąd OpenAI API: {str(e)}")

def _run_openrouter(config, system_prompt, user_message):
    api_key = get_api_key(config, "openrouter")
    if not api_key:
        return _make_result("Brak klucza API OpenRouter. Ustaw OPENROUTER_API_KEY lub dodaj klucz w Ustawieniach.")
    try:
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        model = config.get("ai_model", "openai/gpt-4o")
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        return _make_result(response.choices[0].message.content, getattr(response, "usage", None))
    except Exception as e:
        return _make_result(f"Błąd OpenRouter API: {str(e)}")

def run_chat(config, messages, system_prompt=""):
    """Send a multi-turn chat conversation to the configured chat model.

    Always returns a plain string (backward-compatible).
    """
    provider = config.get("chat_provider") or config.get("ai_provider", "anthropic")
    model = config.get("chat_model") or config.get("ai_model", "claude-sonnet-4-6")

    if provider == "anthropic":
        api_key = get_api_key(config, "anthropic")
        if not api_key:
            return "Brak klucza API Anthropic. Ustaw ANTHROPIC_API_KEY lub dodaj klucz w Ustawieniach."
        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            return f"Błąd Anthropic: {e}"

    elif provider in ("openai", "openrouter"):
        key_name = "openrouter" if provider == "openrouter" else "openai"
        api_key = get_api_key(config, key_name)
        if not api_key:
            env_hint = "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"
            return f"Brak klucza API {provider}. Ustaw {env_hint} lub dodaj klucz w Ustawieniach."
        try:
            kwargs = {"api_key": api_key}
            if provider == "openrouter":
                kwargs["base_url"] = "https://openrouter.ai/api/v1"
            client = openai.OpenAI(**kwargs)
            oai_messages = []
            if system_prompt:
                oai_messages.append({"role": "system", "content": system_prompt})
            oai_messages.extend(messages)
            response = client.chat.completions.create(
                model=model,
                max_tokens=2048,
                messages=oai_messages,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Błąd {provider}: {e}"

    return "Nieznany dostawca AI dla czatu."


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


def generate_instrument_profile(config, symbol, name, category):
    """Generate a one-time AI profile for an instrument (cached by caller)."""
    provider = config.get("ai_provider", "anthropic")
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

    if provider == "anthropic":
        return _result_text(_run_anthropic(config, system, user_msg))
    elif provider == "openai":
        return _result_text(_run_openai(config, system, user_msg))
    elif provider == "openrouter":
        return _result_text(_run_openrouter(config, system, user_msg))
    else:
        return "Błąd: nieznany dostawca AI."
