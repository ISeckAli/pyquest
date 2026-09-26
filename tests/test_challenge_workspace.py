"""
Tests for the challenge workspace page (spec FR05): who gets the editor,
what settings it receives, and that nothing secret reaches the page.

The editor itself runs as JavaScript in the browser, which pytest cannot
execute; its behaviour is checked by hand in the browser.
"""

import json
import re

import pytest

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount
from app.services.challenges import add_test_case, create_challenge, create_topic, publish

HIDDEN_ANSWER = "SECRET-EXPECTED-OUTPUT"
REFERENCE_MARKER = "REFERENCE-SOLUTION-MARKER"

# Starter code that tries to close the settings <script> block and inject
# HTML. tojson must escape it so it stays plain data.
TRICKY_STARTER = "text = input()\n</script><b>not html</b>"


def make_account(email, *roles):
    person = Person(display_name=email.split("@")[0], email=email)
    for role in roles:
        person.add_role(role)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account])
    if RoleType.LEARNER in roles:
        db.session.add(LearnerProfile(person=person))
    db.session.commit()
    return account


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


def editor_config(html):
    """The JSON settings block the page hands to challenge.js, or None."""
    match = re.search(r'<script type="application/json" id="challenge-data">(.*?)</script>', html, re.S)
    return json.loads(match.group(1)) if match else None


@pytest.fixture
def challenge(app):
    topic = create_topic("Strings", sort_order=1)
    challenge = create_challenge(
        None, "Reverse a String", "Print the input reversed.", topic, "beginner",
        starter_code=TRICKY_STARTER,
        reference_solution=f"print('{REFERENCE_MARKER}')",
    )
    add_test_case(challenge, "abc", "cba", is_hidden=False)
    add_test_case(challenge, HIDDEN_ANSWER[::-1], HIDDEN_ANSWER, is_hidden=True)
    add_test_case(challenge, "zz", "zz", is_hidden=True)
    publish(challenge)
    return challenge


def page(client, challenge):
    return client.get(f"/challenges/{challenge.slug}").get_data(as_text=True)


def test_learners_get_the_editor_and_its_settings(client, challenge):
    sign_in(client, make_account("learner@example.com", RoleType.LEARNER))

    html = page(client, challenge)
    config = editor_config(html)

    assert 'id="editor"' in html
    assert 'name="csrf-token"' in html
    assert config["starterCode"] == TRICKY_STARTER
    assert config["testsUrl"] == "/api/challenges/reverse-a-string/tests"
    assert config["submitUrl"] == "/api/challenges/reverse-a-string/submissions"


def test_starter_code_cannot_break_out_of_the_page(client, challenge):
    sign_in(client, make_account("learner@example.com", RoleType.LEARNER))

    assert "</script><b>not html</b>" not in page(client, challenge)


def test_learner_page_still_hides_answers_and_solution(client, challenge):
    sign_in(client, make_account("learner@example.com", RoleType.LEARNER))

    html = page(client, challenge)

    assert HIDDEN_ANSWER not in html
    assert REFERENCE_MARKER not in html


def test_visitors_are_invited_to_log_in(client, challenge):
    html = page(client, challenge)

    assert 'id="editor"' not in html
    assert "/login?next=" in html


def test_staff_without_learner_role_see_an_explanation(client, challenge):
    sign_in(client, make_account("staff@example.com", RoleType.INSTRUCTOR))

    html = page(client, challenge)

    assert 'id="editor"' not in html
    assert "learner account" in html


def test_instructor_preview_has_no_editor(client, challenge):
    sign_in(client, make_account("admin@example.com", RoleType.SYSTEM_ADMINISTRATOR))

    response = client.get(f"/instructor/challenges/{challenge.id}/preview")

    assert response.status_code == 200
    assert 'id="editor"' not in response.get_data(as_text=True)