"""
Tests for the Gemini busy retry and the guest chat wording (Part 13).
"""

import pytest

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount
from app.services.ai_service import AIUnavailableError, BUSY_RETRY_DELAY_SECONDS, build_provider
from app.services.challenges import add_test_case, create_challenge, create_topic, publish


class GeminiError(Exception):
    """Stands in for google-genai's errors, which carry an HTTP status code."""

    def __init__(self, code):
        super().__init__(f"{code} error")
        self.code = code


class Reply:
    text = "A helpful hint."


def gemini_with(outcomes):
    """A Gemini provider whose requests return or raise the given outcomes in
    order, and which records its pauses instead of waiting."""
    provider = build_provider({
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "dummy-key-for-tests",
        "AI_MODEL": "test-model",
        "AI_TIMEOUT_SECONDS": 20,
    })
    pauses = []
    provider._sleep = pauses.append
    queue = list(outcomes)

    def fake_request(system_instruction, prompt):
        outcome = queue.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    provider._request = fake_request
    return provider, pauses, queue


# ---------------------------------------------------------------------------
# Gemini busy retry
# ---------------------------------------------------------------------------

def test_a_busy_gemini_is_tried_once_more_after_a_pause():
    provider, pauses, _ = gemini_with([GeminiError(503), Reply()])

    assert provider.generate("rules", "prompt") == "A helpful hint."
    assert pauses == [BUSY_RETRY_DELAY_SECONDS]


def test_busy_twice_gives_up_after_one_retry():
    provider, pauses, queue = gemini_with([GeminiError(503), GeminiError(503), Reply()])

    with pytest.raises(AIUnavailableError):
        provider.generate("rules", "prompt")
    assert len(pauses) == 1
    assert len(queue) == 1  # the third outcome was never requested


def test_other_errors_are_not_retried():
    provider, pauses, _ = gemini_with([GeminiError(504), Reply()])

    with pytest.raises(AIUnavailableError):
        provider.generate("rules", "prompt")
    assert pauses == []


# ---------------------------------------------------------------------------
# Guest chat wording
# ---------------------------------------------------------------------------

@pytest.fixture
def challenge(app):
    topic = create_topic("Strings", sort_order=1)
    challenge = create_challenge(
        None, "One", "Solve it.", topic, "beginner", reference_solution="print(1)"
    )
    for hidden in (False, True, True):
        add_test_case(challenge, "", "1", is_hidden=hidden)
    publish(challenge)
    return challenge


def page_text(client, challenge):
    return " ".join(client.get(f"/challenges/{challenge.slug}").get_data(as_text=True).split())


def test_guests_are_told_their_real_chat_allowance(client, challenge):
    client.post("/guest")

    text = page_text(client, challenge)

    assert "As a guest you can send 5 messages" in text
    assert "messages a day" not in text


def test_learners_see_the_daily_chat_allowance(client, challenge):
    person = Person(display_name="Ada", email="ada@example.com")
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account, LearnerProfile(person=person)])
    db.session.commit()
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True

    assert "Up to 20 messages a day" in page_text(client, challenge)