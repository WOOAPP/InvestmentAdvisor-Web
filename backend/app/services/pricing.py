"""Hardcoded LLM pricing per provider/model.

Prices are in USD per 1 million tokens (MTok).
Sources:
  Anthropic: claude.com/pricing#api
  OpenAI:    openai.com/api/pricing/
"""

# {provider: {model: (input_usd_per_mtok, output_usd_per_mtok)}}
_PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "anthropic": {
        "claude-opus-4-6":          (15.00, 75.00),
        "claude-sonnet-4-6":        ( 3.00, 15.00),
        "claude-haiku-4-5-20251001":( 0.80,  4.00),
        # aliases / older names
        "claude-opus-4":            (15.00, 75.00),
        "claude-sonnet-4":          ( 3.00, 15.00),
        "claude-haiku-4":           ( 0.80,  4.00),
    },
    "openai": {
        "gpt-4.1":          (2.00,  8.00),
        "gpt-4.1-mini":     (0.40,  1.60),
        "gpt-4.1-nano":     (0.10,  0.40),
        "gpt-4o":           (2.50, 10.00),
        "gpt-4o-mini":      (0.15,  0.60),
        "gpt-4-turbo":      (10.00, 30.00),
        "o1":               (15.00, 60.00),
        "o1-preview":       (15.00, 60.00),
        "o1-mini":          ( 3.00, 12.00),
        "o3":               (10.00, 40.00),
        "o3-mini":          ( 1.10,  4.40),
        "o4-mini":          ( 1.10,  4.40),
    },
}


def calculate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """Return cost in USD for the given token counts.

    Falls back to 0.0 if provider/model is unknown.
    For OpenRouter routes, strips the 'provider/' prefix from model.
    """
    p = provider.lower()
    m = model.lower()

    # OpenRouter: try to match by the model slug (after the slash)
    if p == "openrouter" and "/" in m:
        slug = m.split("/", 1)[1]
        # Try to find slug in openai or anthropic tables
        for sub_provider in ("openai", "anthropic"):
            rates = _PRICING.get(sub_provider, {})
            if slug in rates:
                in_rate, out_rate = rates[slug]
                return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000
        return 0.0

    rates = _PRICING.get(p, {})
    if m not in rates:
        return 0.0
    in_rate, out_rate = rates[m]
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000
