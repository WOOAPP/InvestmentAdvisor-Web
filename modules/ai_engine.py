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
            "o1-preview"
        ]
    }
    return models.get(provider, [])