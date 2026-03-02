"""Tests for ai_engine.py — provider dispatch, result helpers, prompt builders."""

import unittest
import sys, os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import modules.ai_engine as ai


# ── _make_result / _result_text ──────────────────────────────────
class TestMakeResult(unittest.TestCase):

    def test_text_only(self):
        r = ai._make_result("hello")
        self.assertEqual(r["text"], "hello")
        self.assertEqual(r["input_tokens"], 0)
        self.assertEqual(r["output_tokens"], 0)

    def test_with_anthropic_usage(self):
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 200
        r = ai._make_result("ok", usage)
        self.assertEqual(r["input_tokens"], 100)
        self.assertEqual(r["output_tokens"], 200)

    def test_with_openai_usage(self):
        usage = MagicMock(spec=[])
        usage.prompt_tokens = 50
        usage.completion_tokens = 75
        # openai usage doesn't have input_tokens
        del usage.input_tokens
        del usage.output_tokens
        # Simulate getattr fallback chain
        usage2 = type("U", (), {
            "prompt_tokens": 50,
            "completion_tokens": 75,
        })()
        r = ai._make_result("ok", usage2)
        self.assertEqual(r["input_tokens"], 50)
        self.assertEqual(r["output_tokens"], 75)

    def test_none_usage(self):
        r = ai._make_result("text", None)
        self.assertEqual(r["input_tokens"], 0)
        self.assertEqual(r["output_tokens"], 0)


class TestResultText(unittest.TestCase):

    def test_dict_input(self):
        self.assertEqual(ai._result_text({"text": "hello", "input_tokens": 0}), "hello")

    def test_string_input(self):
        self.assertEqual(ai._result_text("plain"), "plain")

    def test_empty_dict(self):
        self.assertEqual(ai._result_text({}), "")


# ── _call_provider ───────────────────────────────────────────────
class TestCallProviderAnthropic(unittest.TestCase):

    @patch("modules.ai_engine.anthropic")
    def test_anthropic_call(self, mock_anthropic):
        client = MagicMock()
        mock_anthropic.Anthropic.return_value = client
        response = MagicMock()
        response.content = [MagicMock(text="AI response")]
        usage = MagicMock()
        usage.input_tokens = 10
        usage.output_tokens = 20
        response.usage = usage
        client.messages.create.return_value = response

        text, u = ai._call_provider(
            "anthropic", "key123", "claude-opus-4-6",
            "system prompt", [{"role": "user", "content": "hi"}])

        self.assertEqual(text, "AI response")
        mock_anthropic.Anthropic.assert_called_once_with(api_key="key123")
        client.messages.create.assert_called_once()
        call_kwargs = client.messages.create.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "claude-opus-4-6")
        self.assertEqual(call_kwargs.kwargs["system"], "system prompt")


class TestCallProviderOpenAI(unittest.TestCase):

    @patch("modules.ai_engine.openai")
    def test_openai_call(self, mock_openai):
        client = MagicMock()
        mock_openai.OpenAI.return_value = client
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="GPT response"))]
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=10)
        client.chat.completions.create.return_value = response

        text, u = ai._call_provider(
            "openai", "sk-key", "gpt-4o",
            "system", [{"role": "user", "content": "test"}])

        self.assertEqual(text, "GPT response")
        mock_openai.OpenAI.assert_called_once_with(api_key="sk-key")

    @patch("modules.ai_engine.openai")
    def test_openrouter_uses_base_url(self, mock_openai):
        client = MagicMock()
        mock_openai.OpenAI.return_value = client
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="OR response"))]
        response.usage = None
        client.chat.completions.create.return_value = response

        ai._call_provider(
            "openrouter", "or-key", "openai/gpt-4o",
            "sys", [{"role": "user", "content": "hi"}])

        call_kwargs = mock_openai.OpenAI.call_args.kwargs
        self.assertEqual(call_kwargs["base_url"], "https://openrouter.ai/api/v1")

    @patch("modules.ai_engine.openai")
    def test_system_prompt_prepended(self, mock_openai):
        client = MagicMock()
        mock_openai.OpenAI.return_value = client
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="ok"))]
        response.usage = None
        client.chat.completions.create.return_value = response

        ai._call_provider(
            "openai", "key", "gpt-4o",
            "be helpful", [{"role": "user", "content": "q"}])

        msgs = client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[0]["content"], "be helpful")
        self.assertEqual(msgs[1]["role"], "user")


# ── _run_provider ────────────────────────────────────────────────
class TestRunProvider(unittest.TestCase):

    def test_unknown_provider(self):
        config = {"ai_provider": "unknown"}
        result = ai._run_provider(config, "sys", "msg")
        self.assertIn("nieznany", result["text"].lower())

    @patch("modules.ai_engine.get_api_key", return_value="")
    def test_missing_api_key(self, _):
        config = {"ai_provider": "anthropic"}
        result = ai._run_provider(config, "sys", "msg")
        self.assertIn("Brak klucza", result["text"])

    @patch("modules.ai_engine._call_provider")
    @patch("modules.ai_engine.get_api_key", return_value="key123")
    def test_success(self, _, mock_call):
        mock_call.return_value = ("analysis", None)
        config = {"ai_provider": "anthropic", "ai_model": "claude-opus-4-6"}
        result = ai._run_provider(config, "sys", "msg")
        self.assertEqual(result["text"], "analysis")

    @patch("modules.ai_engine._call_provider", side_effect=ConnectionError("timeout"))
    @patch("modules.ai_engine.get_api_key", return_value="key123")
    def test_exception_handled(self, _, __):
        config = {"ai_provider": "anthropic"}
        result = ai._run_provider(config, "sys", "msg")
        self.assertIn("Błąd", result["text"])
        self.assertIn("timeout", result["text"])


# ── run_analysis ─────────────────────────────────────────────────
class TestRunAnalysis(unittest.TestCase):

    @patch("modules.ai_engine._run_provider")
    def test_uses_macro_prompt_when_available(self, mock_run):
        mock_run.return_value = {"text": "ok", "input_tokens": 0, "output_tokens": 0}
        config = {"prompt": "analyze"}
        ai.run_analysis(config, "market", [], macro_text="macro data")
        user_msg = mock_run.call_args[0][2]
        self.assertIn("macro data", user_msg)

    @patch("modules.ai_engine._run_provider")
    def test_uses_legacy_prompt_without_macro(self, mock_run):
        mock_run.return_value = {"text": "ok", "input_tokens": 0, "output_tokens": 0}
        config = {"prompt": "analyze"}
        ai.run_analysis(config, "market", [{"title": "news", "source": "bbc"}])
        user_msg = mock_run.call_args[0][2]
        self.assertIn("market", user_msg)


# ── run_chat ─────────────────────────────────────────────────────
class TestRunChat(unittest.TestCase):

    def test_unknown_provider_returns_string(self):
        config = {"chat_provider": "nonexistent"}
        result = ai.run_chat(config, [{"role": "user", "content": "hi"}])
        self.assertIsInstance(result, str)
        self.assertIn("Nieznany", result)

    @patch("modules.ai_engine.get_api_key", return_value="")
    def test_missing_key(self, _):
        config = {"chat_provider": "anthropic"}
        result = ai.run_chat(config, [{"role": "user", "content": "hi"}])
        self.assertIn("Brak klucza", result)

    @patch("modules.ai_engine._call_provider", return_value=("reply", None))
    @patch("modules.ai_engine.get_api_key", return_value="key")
    def test_success_returns_string(self, _, __):
        config = {"chat_provider": "anthropic", "chat_model": "claude-sonnet-4-6"}
        result = ai.run_chat(config, [{"role": "user", "content": "hi"}])
        self.assertEqual(result, "reply")

    @patch("modules.ai_engine._call_provider", side_effect=TimeoutError("fail"))
    @patch("modules.ai_engine.get_api_key", return_value="key")
    def test_exception_returns_error_string(self, _, __):
        config = {"chat_provider": "openai", "chat_model": "gpt-4o"}
        result = ai.run_chat(config, [{"role": "user", "content": "hi"}])
        self.assertIn("Błąd", result)

    @patch("modules.ai_engine._call_provider", return_value=("r", None))
    @patch("modules.ai_engine.get_api_key", return_value="key")
    def test_falls_back_to_ai_provider(self, _, __):
        config = {"ai_provider": "openai", "ai_model": "gpt-4o"}
        result = ai.run_chat(config, [{"role": "user", "content": "hi"}])
        self.assertEqual(result, "r")


# ── generate_instrument_profile ──────────────────────────────────
class TestGenerateInstrumentProfile(unittest.TestCase):

    @patch("modules.ai_engine._run_provider")
    def test_returns_text(self, mock_run):
        mock_run.return_value = {"text": "Profile text", "input_tokens": 0, "output_tokens": 0}
        config = {"ai_provider": "anthropic"}
        result = ai.generate_instrument_profile(config, "AAPL", "Apple", "Akcje")
        self.assertEqual(result, "Profile text")
        user_msg = mock_run.call_args[0][2]
        self.assertIn("Apple", user_msg)
        self.assertIn("AAPL", user_msg)
        self.assertIn("Akcje", user_msg)

    @patch("modules.ai_engine._run_provider")
    def test_uses_custom_profile_prompt(self, mock_run):
        mock_run.return_value = {"text": "ok", "input_tokens": 0, "output_tokens": 0}
        config = {"ai_provider": "anthropic", "profile_prompt": "Custom prompt here"}
        ai.generate_instrument_profile(config, "X", "X Co", "Inne")
        user_msg = mock_run.call_args[0][2]
        self.assertIn("Custom prompt here", user_msg)


# ── get_available_models ─────────────────────────────────────────
class TestGetAvailableModels(unittest.TestCase):

    def test_anthropic_models(self):
        models = ai.get_available_models("anthropic")
        self.assertIn("claude-opus-4-6", models)

    def test_openai_models(self):
        models = ai.get_available_models("openai")
        self.assertIn("gpt-4o", models)

    def test_openrouter_models(self):
        models = ai.get_available_models("openrouter")
        self.assertTrue(len(models) > 0)

    def test_unknown_provider_empty(self):
        models = ai.get_available_models("unknown")
        self.assertEqual(models, [])


# ── Prompt builders ──────────────────────────────────────────────
class TestBuildMacroPrompt(unittest.TestCase):

    def test_includes_market_and_macro(self):
        result = ai._build_macro_prompt("market data", "macro trend")
        self.assertIn("market data", result)
        self.assertIn("macro trend", result)

    def test_includes_scraped(self):
        result = ai._build_macro_prompt("m", "mt", "scraped content")
        self.assertIn("scraped content", result)
        self.assertIn("TREŚĆ ZE ŹRÓDEŁ WWW", result)

    def test_no_scraped(self):
        result = ai._build_macro_prompt("m", "mt", "")
        self.assertNotIn("TREŚĆ ZE ŹRÓDEŁ WWW", result)


class TestBuildLegacyPrompt(unittest.TestCase):

    def test_includes_news(self):
        news = [{"title": "War update", "source": "BBC", "description": "Details here"}]
        result = ai._build_legacy_prompt("market", news)
        self.assertIn("War update", result)
        self.assertIn("BBC", result)

    def test_skips_error_news(self):
        news = [{"error": "no data"}]
        result = ai._build_legacy_prompt("market", news)
        self.assertNotIn("WIADOMOŚCI", result)

    def test_empty_news(self):
        result = ai._build_legacy_prompt("market", [])
        self.assertIn("market", result)


if __name__ == "__main__":
    unittest.main()
