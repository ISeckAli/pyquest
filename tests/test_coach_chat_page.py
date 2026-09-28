"""
Tests for how chat, review, and ratings appear on the challenge page (spec
PR-C3, PR-C4, PR-C6). The buttons run as JavaScript and are checked in the
browser.
"""

import json
import re

import pytest

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount
from app.services.challenges import add_test_case, create_challenge, create_topic, publish
from app.services.coach_chat import ask_coach


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


def test_learners_get_chat_review_and_rating_settings(client, challenge):
    sign_in(client, make_learner())

    html = page(client, challenge)
    config = editor_config(html)

    assert 'id="chat-form"' in html
    assert 'id="review-button"' in html
    assert "js/coach-chat.js" in html
    assert config["chatUrl"] == "/api/challenges/reverse-a-string/chat"
    assert config["reviewUrl"] == "/api/challenges/reverse-a-string/review"
    assert config["ratingUrlTemplate"] == "/api/coach-messages/{id}/rating"
    assert config["chat"] == []
    assert config["review"] is None


def test_earlier_conversation_comes_back_with_the_page(client, challenge):
    learner = make_learner()
    ask_coach(learner, challenge, "How do I start?", "text = input()")
    sign_in(client, learner)

    chat = editor_config(page(client, challenge))["chat"]

    assert [message["sender"] for message in chat] == ["learner", "coach"]
    assert chat[0]["text"] == "How do I start?"


def test_visitors_do_not_see_the_chat(client, challenge):
    assert 'id="chat-form"' not in page(client, challenge)