import anthropic
import openai
from datetime import datetime

def run_analysis(config, market_summary, news_list, scraped_text=""):
    """Wysyła dane do wybranego modelu AI i zwraca analizę."""
    provider = config.get("ai_provider", "anthropic")
    prompt = config.get("prompt", "Przeanalizuj sytuację rynkową.")

    # Przygotuj wiadomości z newsami
    news_text = ""
    if news_list and not any("error" in n for n in news_list):
        news_text = "\n=== AKTUALNE WIADOMOŚCI ===\n"
        for i, n in enumerate(news_list[:8], 1):
            news_text += f"{i}. [{n.get('source','')}] {n.get('title','')}\n"
            if n.get("description"):
                news_text += f"   {n.get('description','')[:150]}...\n"

    full_message = (
        f"Data analizy: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"{market_summary}\n"
        f"{news_text}\n"
        f"{'=== TREŚĆ ZE ŹRÓDEŁ WWW ===' + chr(10) + scraped_text if scraped_text else ''}\n\n"
        f"Na podstawie powyższych danych przeprowadź szczegółową analizę."
    )

    if provider == "anthropic":
        return _run_anthropic(config, prompt, full_message)
    elif provider == "openai":
        return _run_openai(config, prompt, full_message)
    elif provider == "openrouter":
        return _run_openrouter(config, prompt, full_message)
    else:
        return "Błąd: nieznany dostawca AI. Sprawdź ustawienia."

def _run_anthropic(config, system_prompt, user_message):
    api_key = config["api_keys"].get("anthropic", "")
    if not api_key:
        return "Błąd: brak klucza API Anthropic. Dodaj go w Ustawieniach."
    try:
        client = anthropic.Anthropic(api_key=api_key)
        model = config.get("ai_model", "claude-opus-4-6")
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Błąd Anthropic API: {str(e)}"

def _run_openai(config, system_prompt, user_message):
    api_key = config["api_keys"].get("openai", "")
    if not api_key:
        return "Błąd: brak klucza API OpenAI. Dodaj go w Ustawieniach."
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
        return response.choices[0].message.content
    except Exception as e:
        return f"Błąd OpenAI API: {str(e)}"

def _run_openrouter(config, system_prompt, user_message):
    api_key = config["api_keys"].get("openrouter", "")
    if not api_key:
        return "Błąd: brak klucza API OpenRouter. Dodaj go w Ustawieniach."
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
        return response.choices[0].message.content
    except Exception as e:
        return f"Błąd OpenRouter API: {str(e)}"

def run_chat(config, messages, system_prompt=""):
    """Send a multi-turn chat conversation to the configured chat model.

    config: full app config dict (uses chat_provider, chat_model, api_keys)
    messages: list of {"role": "user"|"assistant", "content": "..."}
    system_prompt: system-level instruction (e.g. analysis context)
    Returns: assistant reply string
    """
    provider = config.get("chat_provider") or config.get("ai_provider", "anthropic")
    model = config.get("chat_model") or config.get("ai_model", "claude-sonnet-4-6")
    api_keys = config.get("api_keys", {})

    if provider == "anthropic":
        api_key = api_keys.get("anthropic", "")
        if not api_key:
            return "Brak klucza API Anthropic. Dodaj go w Ustawieniach."
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
        api_key = api_keys.get(key_name, "")
        if not api_key:
            return f"Brak klucza API {provider}. Dodaj go w Ustawieniach."
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
