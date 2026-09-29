"""
Provider-agnostic AI layer (spec DR-02, section 9).

This is the only module that knows which AI company PyQuest uses. The rest
of the app calls generate() and never imports a provider's library, so
switching providers means adding one class here and changing the
AI_PROVIDER setting; no feature code changes.

Providers:
    gemini    Google Gemini (free tier, spec DR-11)
    fake      canned replies for automated tests: no network, no quota
    disabled  used when AI is switched off or no key is configured

Every provider failure (no network, timeout, quota used up, a bad key) is
raised as AIUnavailableError, so callers handle one error type and can
always fall back to instructor-written hints (spec NFR05).

What gets sent to a provider is decided by the Coach service
(app/services/coach.py), which owns the rules about never sending hidden
tests, reference solutions, or personal details.
"""

import time

from flask import current_app

# Longest part of a provider's error message kept for logs and diagnostics.
MAX_ERROR_DETAIL = 300

# Gemini rejects requests that allow less time than this to reply.
GEMINI_MIN_TIMEOUT_SECONDS = 10

# Gemini answers 503 ("this model is experiencing high demand") when it is
# busy, which usually clears within seconds. Such a request is tried once
# more after this pause before giving up. Timeouts are not retried (the
# learner has already waited), and neither are other errors, which would
# not fix themselves.
GEMINI_BUSY_STATUS = 503
BUSY_RETRY_DELAY_SECONDS = 1.5


class AIUnavailableError(Exception):
    """The AI provider could not produce an answer."""


class AIProvider:
    """The interface every provider implements."""

    name = "base"

    def generate(self, system_instruction, prompt):
        """Return the model's reply to prompt as plain text.

        Args:
            system_instruction: standing rules for the model (its role and
                what it must never do), kept separate from the prompt.
            prompt: the request itself.

        Raises:
            AIUnavailableError: if no usable reply could be produced.
        """
        raise NotImplementedError


class GeminiProvider(AIProvider):
    """Google Gemini through the official google-genai library."""

    name = "gemini"

    def __init__(self, api_key, model, timeout_seconds, sleep=time.sleep):
        # Imported here rather than at the top of the module, so the app
        # and the test suite start without loading Google's library when
        # Gemini is not the configured provider.
        from google import genai
        from google.genai import types

        self._types = types
        self._model = model
        # How to wait before a retry. Tests pass their own, so they can
        # check the retry without actually waiting.
        self._sleep = sleep

        # Never below Gemini's minimum, even if the setting is lowered.
        # The library takes its timeout in milliseconds.
        timeout = max(timeout_seconds, GEMINI_MIN_TIMEOUT_SECONDS)
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
        )

    def _request(self, system_instruction, prompt):
        types = self._types
        return self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                # Low randomness: hints should be consistent and on topic
                # rather than creative.
                temperature=0.4,
                max_output_tokens=1024,
                # Automatic function calling lets a model trigger code in
                # the application. PyQuest never gives the model any
                # functions to call, so it is switched off explicitly.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )

    def generate(self, system_instruction, prompt):
        for attempt in (1, 2):
            try:
                response = self._request(system_instruction, prompt)
                break
            except Exception as error:
                # Deliberately broad: whatever goes wrong inside the
                # provider (network, timeout, quota, a changed API), the
                # caller only needs to know that no answer is available and
                # fall back. Only a first "busy" answer is worth one retry.
                if attempt == 1 and getattr(error, "code", None) == GEMINI_BUSY_STATUS:
                    self._sleep(BUSY_RETRY_DELAY_SECONDS)
                    continue
                detail = f"{type(error).__name__}: {error}"[:MAX_ERROR_DETAIL]
                raise AIUnavailableError(f"Gemini request failed. {detail}") from error

        text = (response.text or "").strip()
        if not text:
            raise AIUnavailableError("Gemini returned an empty reply.")
        return text


class FakeProvider(AIProvider):
    """A stand-in for tests.

    Returns queued replies in order (or a default reply), records every
    request so tests can inspect exactly what would have been sent, and
    can be told to fail to test fallbacks.
    """

    name = "fake"
    DEFAULT_REPLY = "Look closely at what the examples have in common."

    def __init__(self):
        self.replies = []
        self.calls = []
        self.fail = False

    def generate(self, system_instruction, prompt):
        self.calls.append({"system_instruction": system_instruction, "prompt": prompt})
        if self.fail:
            raise AIUnavailableError("Simulated provider failure.")
        return self.replies.pop(0) if self.replies else self.DEFAULT_REPLY


class DisabledProvider(AIProvider):
    """Used when AI is switched off or not configured: always unavailable,
    so every Coach feature falls back to instructor-written content."""

    name = "disabled"

    def __init__(self, reason):
        self.reason = reason

    def generate(self, system_instruction, prompt):
        raise AIUnavailableError(self.reason)


def build_provider(config):
    """Create the provider named by config["AI_PROVIDER"]."""
    name = config.get("AI_PROVIDER") or "disabled"

    if name == "gemini":
        api_key = config.get("GEMINI_API_KEY")
        if not api_key:
            return DisabledProvider("AI_PROVIDER is gemini but GEMINI_API_KEY is not set.")
        return GeminiProvider(api_key, config["AI_MODEL"], config["AI_TIMEOUT_SECONDS"])

    if name == "fake":
        return FakeProvider()

    return DisabledProvider("AI features are switched off (AI_PROVIDER is not set).")


def get_provider():
    """The current app's provider, created on first use and then reused."""
    provider = current_app.extensions.get("pyquest_ai_provider")
    if provider is None:
        provider = build_provider(current_app.config)
        current_app.extensions["pyquest_ai_provider"] = provider
    return provider


def generate(system_instruction, prompt):
    """Ask the configured provider for a reply. See AIProvider.generate."""
    return get_provider().generate(system_instruction, prompt)