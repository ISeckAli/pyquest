"""
Tests for how the AI Coach appears on the challenge page (spec 5.9).
The buttons themselves run as JavaScript and are checked in the browser.
"""

import json
import re

import pytest

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount
from app.services.challenges import add_test_case, create_challenge, create_topic, publish
from app.services.coach import get_hint


def make_learner():
    person = Person(display_name="learner", email="learner@example.com")
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


def editor_config(html):
    match = re.search(r'<script type="application/json" id="challenge-data">(.*?)</script>', html, re.S)
    return json.loads(match.group(1))


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


def page(client, challenge):
    return client.get(f"/challenges/{challenge.slug}").get_data(as_text=True)


def test_learners_get_the_coach_and_its_settings(client, challenge):
    sign_in(client, make_learner())

    html = page(client, challenge)
    config = editor_config(html)

    assert 'id="hint-button"' in html
    assert "lowers the XP" in html
    assert config["hintsUrl"] == "/api/challenges/reverse-a-string/hints"
    assert config["explanationUrlTemplate"] == "/api/submissions/{id}/explanation"
    assert config["maxHints"] == 3
    assert config["hints"] == []


def test_hints_already_received_come_back_with_the_page(client, challenge):
    learner = make_learner()
    get_hint(learner, challenge, "text = input()")
    sign_in(client, learner)

    hints = editor_config(page(client, challenge))["hints"]

    assert len(hints) == 1
    assert hints[0]["level"] == 1
    assert hints[0]["source"] == "ai"


def test_visitors_do_not_see_the_coach(client, challenge):
    assert 'id="hint-button"' not in page(client, challenge)