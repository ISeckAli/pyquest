"""
Tests for the provider-agnostic AI layer (spec DR-02).

No test here contacts a real AI service: the testing configuration uses the
fake provider, and the Gemini tests replace the network call.
"""

import pytest

from app.services.ai_service import (
    AIUnavailableError,
    DisabledProvider,
    FakeProvider,
    GeminiProvider,
    build_provider,
    generate,
    get_provider,
)


def test_tests_use_the_fake_provider(app):
    assert isinstance(get_provider(), FakeProvider)


def test_fake_provider_returns_queued_replies_and_records_requests(app):
    provider = get_provider()
    provider.replies = ["first reply"]

    reply = generate("be helpful", "a question")

    assert reply == "first reply"
    assert provider.calls == [{"system_instruction": "be helpful", "prompt": "a question"}]
    assert generate("be helpful", "again") == FakeProvider.DEFAULT_REPLY


def test_fake_provider_can_simulate_failure(app):
    get_provider().fail = True

    with pytest.raises(AIUnavailableError):
        generate("be helpful", "a question")


def test_ai_is_off_when_no_provider_is_configured():
    provider = build_provider({"AI_PROVIDER": None})

    assert isinstance(provider, DisabledProvider)
    with pytest.raises(AIUnavailableError):
        provider.generate("rules", "prompt")


def test_gemini_without_a_key_is_disabled():
    provider = build_provider({"AI_PROVIDER": "gemini", "GEMINI_API_KEY": None})

    assert isinstance(provider, DisabledProvider)


def gemini_provider():
    """A Gemini provider with a dummy key. Creating it makes no network call."""
    return build_provider({
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "dummy-key-for-tests",
        "AI_MODEL": "test-model",
        "AI_TIMEOUT_SECONDS": 8,
    })


def test_gemini_is_used_when_a_key_is_set():
    assert isinstance(gemini_provider(), GeminiProvider)


def test_gemini_errors_become_ai_unavailable(monkeypatch):
    provider = gemini_provider()

    def broken_call(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(provider._client.models, "generate_content", broken_call)

    with pytest.raises(AIUnavailableError, match="network down"):
        provider.generate("rules", "prompt")


def test_ai_check_command_reports_a_working_provider(app):
    result = app.test_cli_runner().invoke(args=["ai-check"])

    assert result.exit_code == 0
    assert "Provider: fake" in result.output


def test_ai_check_command_reports_failure(app):
    get_provider().fail = True

    result = app.test_cli_runner().invoke(args=["ai-check"])

    assert result.exit_code != 0
    assert "AI is unavailable" in result.output