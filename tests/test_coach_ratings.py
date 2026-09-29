"""
Tests for ratings on hints and failure explanations (spec PR-C6), which
complete ratings on every kind of Coach reply.
"""

import json
import re

import pytest

from app.extensions import db
from app.models import Hint, LearnerProfile, Person, RoleType, UserAccount
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


def get_hint(client, challenge):
    return client.post(f"/api/challenges/{challenge.slug}/hints", json={"code": "x"}).get_json()


def rate_hint(client, hint_id, rating):
    return client.post(f"/api/hints/{hint_id}/rating", json={"rating": rating})


def test_hint_responses_include_an_id_to_rate(client, learner, challenge):
    hint = get_hint(client, challenge)

    assert isinstance(hint["id"], int)
    assert hint["rating"] is None


def test_learner_can_rate_their_hint(client, learner, challenge):
    hint = get_hint(client, challenge)

    response = rate_hint(client, hint["id"], "down")

    assert response.get_json()["rating"] == "down"
    assert db.session.get(Hint, hint["id"]).rating == "down"


def test_only_your_own_hints_can_be_rated(client, learner, challenge):
    hint = get_hint(client, challenge)
    sign_in(client, make_learner("other@example.com"))

    assert rate_hint(client, hint["id"], "up").status_code == 404


def test_hint_rating_must_be_up_or_down(client, learner, challenge):
    hint = get_hint(client, challenge)

    assert rate_hint(client, hint["id"], "meh").status_code == 400


def test_explanations_can_be_rated(client, learner, challenge):
    results = [{"test_id": t.id, "output": "wrong"} for t in challenge.test_cases]
    feedback = client.post(
        f"/api/challenges/{challenge.slug}/submissions",
        json={"code": "print('wrong')", "results": results},
    ).get_json()
    explanation = client.post(f"/api/submissions/{feedback['submission_id']}/explanation").get_json()

    response = client.post(
        f"/api/coach-messages/{explanation['id']}/rating", json={"rating": "up"}
    )

    assert response.get_json()["rating"] == "up"


def test_page_brings_back_hint_ratings(client, learner, challenge):
    hint = get_hint(client, challenge)
    rate_hint(client, hint["id"], "up")

    html = client.get(f"/challenges/{challenge.slug}").get_data(as_text=True)
    config = json.loads(
        re.search(r'<script type="application/json" id="challenge-data">(.*?)</script>', html, re.S).group(1)
    )

    assert config["hints"][0]["rating"] == "up"
    assert config["hintRatingUrlTemplate"] == "/api/hints/{id}/rating"