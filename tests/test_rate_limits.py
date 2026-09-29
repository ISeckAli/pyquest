"""
Tests for rate limiting (spec PR-N3).
"""

import pytest

from app import rate_limit as rate_limit_module
from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount
from app.services.challenges import add_test_case, create_challenge, create_topic, publish

WRONG_LOGIN = {"email": "nobody@example.com", "password": "not-the-password"}


@pytest.fixture
def clock(monkeypatch):
    """A controllable clock, so tests can move time forward instantly."""
    now = {"value": 1000.0}
    monkeypatch.setattr(rate_limit_module, "clock", lambda: now["value"])
    return now


def make_learner():
    person = Person(display_name="Ada", email="ada@example.com")
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


def test_logins_beyond_the_limit_get_429_with_retry_after(client, clock):
    for _ in range(10):
        assert client.post("/login", data=WRONG_LOGIN).status_code == 200

    response = client.post("/login", data=WRONG_LOGIN)

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_the_limit_resets_when_its_window_passes(client, clock):
    for _ in range(11):
        client.post("/login", data=WRONG_LOGIN)

    clock["value"] += 61

    assert client.post("/login", data=WRONG_LOGIN).status_code == 200


def test_viewing_pages_is_never_limited(client, clock):
    for _ in range(15):
        assert client.get("/login").status_code == 200


def test_each_visitor_has_their_own_limit(client, clock):
    for _ in range(11):
        client.post("/login", data=WRONG_LOGIN)

    other_visitor = client.post(
        "/login", data=WRONG_LOGIN, environ_base={"REMOTE_ADDR": "203.0.113.9"}
    )

    assert other_visitor.status_code == 200


def test_guest_accounts_are_limited(client, clock):
    for _ in range(5):
        client.post("/guest")
        client.post("/logout")

    assert client.post("/guest").status_code == 429


def test_api_limits_answer_in_json(app, client, clock):
    topic = create_topic("Strings", sort_order=1)
    challenge = create_challenge(
        None, "One", "Solve it.", topic, "beginner", reference_solution="print(1)"
    )
    for hidden in (False, True, True):
        add_test_case(challenge, "", "1", is_hidden=hidden)
    publish(challenge)
    learner = make_learner()
    sign_in(client, learner)
    # Fill this learner's chat allowance for the current window.
    store = app.extensions.setdefault("pyquest_rate_limits", rate_limit_module._Store())
    for _ in range(20):
        store.hit(f"chat:user:{learner.id}", 20, 60, clock["value"])

    response = client.post(f"/api/challenges/{challenge.slug}/chat", json={"message": "Hi"})

    assert response.status_code == 429
    assert "Too many requests" in response.get_json()["error"]


def test_limits_can_be_switched_off(app, client, clock):
    app.config["RATE_LIMITS_ENABLED"] = False

    for _ in range(12):
        assert client.post("/login", data=WRONG_LOGIN).status_code == 200