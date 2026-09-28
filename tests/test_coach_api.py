"""
Tests for the Coach API endpoints (spec PR-C1, PR-C2) and the hint XP cost
(PR-L3). All AI replies come from the fake provider.
"""

import pytest

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount
from app.services.ai_service import get_provider
from app.services.challenges import add_test_case, create_challenge, create_topic, publish


def make_learner(email="learner@example.com"):
    person = Person(display_name=email.split("@")[0], email=email)
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account, LearnerProfile(person=person)])
    db.session.commit()
    return account


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


@pytest.fixture
def learner(client):
    account = make_learner()
    sign_in(client, account)
    return account


@pytest.fixture
def challenge(app):
    topic = create_topic("Strings", sort_order=1)
    challenge = create_challenge(
        None, "Reverse a String", "Print the input reversed.", topic, "beginner",
        reference_solution="print(input()[::-1])",
    )
    add_test_case(challenge, "abc", "cba", is_hidden=False)
    add_test_case(challenge, "hello", "olleh", is_hidden=True)
    add_test_case(challenge, "a", "a", is_hidden=True)
    publish(challenge)
    return challenge


def ask_for_hint(client, challenge, code="text = input()"):
    return client.post(f"/api/challenges/{challenge.slug}/hints", json={"code": code})


def submit(client, challenge, correct):
    results = [
        {"test_id": test.id, "output": test.expected_output if correct else "wrong"}
        for test in challenge.test_cases
    ]
    return client.post(
        f"/api/challenges/{challenge.slug}/submissions",
        json={"code": "print(input()[::-1])", "results": results},
    ).get_json()


# ---------------------------------------------------------------------------
# Hints
# ---------------------------------------------------------------------------

def test_learner_gets_the_next_hint(client, learner, challenge):
    data = ask_for_hint(client, challenge).get_json()

    assert data["level"] == 1
    assert data["source"] == "ai"
    assert data["remaining"] == 2


def test_hints_past_the_limit_get_429(client, learner, challenge):
    for _ in range(3):
        ask_for_hint(client, challenge)

    response = ask_for_hint(client, challenge)

    assert response.status_code == 429
    assert "all 3 hints" in response.get_json()["error"]


def test_hints_require_login(client, challenge):
    assert ask_for_hint(client, challenge).status_code == 401


def test_hint_request_must_be_json(client, learner, challenge):
    response = client.post(
        f"/api/challenges/{challenge.slug}/hints", data="not json", content_type="text/plain"
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Failure explanations
# ---------------------------------------------------------------------------

def test_failed_submission_can_be_explained(client, learner, challenge):
    feedback = submit(client, challenge, correct=False)

    response = client.post(f"/api/submissions/{feedback['submission_id']}/explanation")

    assert response.status_code == 200
    assert response.get_json()["source"] == "ai"


def test_another_learners_submission_is_not_found(client, learner, challenge):
    feedback = submit(client, challenge, correct=False)
    sign_in(client, make_learner("other@example.com"))

    response = client.post(f"/api/submissions/{feedback['submission_id']}/explanation")

    assert response.status_code == 404


def test_passed_submission_cannot_be_explained(client, learner, challenge):
    feedback = submit(client, challenge, correct=True)

    response = client.post(f"/api/submissions/{feedback['submission_id']}/explanation")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Hint XP cost (PR-L3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ai_hints, expected_xp", [(0, 10), (1, 8), (2, 6), (3, 4)])
def test_ai_hints_reduce_first_solve_xp(client, learner, challenge, ai_hints, expected_xp):
    for _ in range(ai_hints):
        ask_for_hint(client, challenge)

    feedback = submit(client, challenge, correct=True)

    assert feedback["xp_awarded"] == expected_xp
    assert feedback["hints_used"] == ai_hints


def test_instructor_fallback_hints_cost_no_xp(client, learner, challenge):
    get_provider().fail = True
    ask_for_hint(client, challenge)
    ask_for_hint(client, challenge)

    feedback = submit(client, challenge, correct=True)

    assert feedback["xp_awarded"] == 10
    assert feedback["hints_used"] == 0