"""
Tests for the instructor reference-solution check endpoint (spec FR12).

This is the one endpoint that sends hidden expected outputs to a browser,
so the tests focus on who may use it.
"""

import pytest

from app.extensions import db
from app.models import Person, RoleType, UserAccount
from app.services.challenges import add_test_case, create_challenge, create_topic

HIDDEN_ANSWER = "olleh"


def make_account(email, *roles):
    person = Person(display_name=email.split("@")[0], email=email)
    for role in roles:
        person.add_role(role)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account])
    db.session.commit()
    return account


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


@pytest.fixture
def author(app):
    return make_account("teach@example.com", RoleType.INSTRUCTOR)


@pytest.fixture
def challenge(author):
    """A draft (never published), since the check runs before publishing."""
    topic = create_topic("Strings", sort_order=1)
    challenge = create_challenge(
        author, "Reverse a String", "Print the input reversed.", topic, "beginner",
        reference_solution="print(input()[::-1])",
    )
    add_test_case(challenge, "abc", "cba", is_hidden=False)
    add_test_case(challenge, "hello", HIDDEN_ANSWER, is_hidden=True)
    return challenge


def check_url(challenge):
    return f"/api/instructor/challenges/{challenge.id}/reference-check"


def test_author_gets_the_solution_and_every_expected_output(client, author, challenge):
    sign_in(client, author)

    data = client.get(check_url(challenge)).get_json()

    assert data["code"] == "print(input()[::-1])"
    assert [test["expected"] for test in data["tests"]] == ["cba", HIDDEN_ANSWER]
    assert [test["hidden"] for test in data["tests"]] == [False, True]


def test_administrators_can_check_any_challenge(client, challenge):
    sign_in(client, make_account("admin@example.com", RoleType.SYSTEM_ADMINISTRATOR))

    assert client.get(check_url(challenge)).status_code == 200


def test_other_instructors_are_refused(client, challenge):
    sign_in(client, make_account("other@example.com", RoleType.INSTRUCTOR))

    response = client.get(check_url(challenge))

    assert response.status_code == 403
    assert HIDDEN_ANSWER not in response.get_data(as_text=True)


def test_learners_are_refused(client, challenge):
    sign_in(client, make_account("learner@example.com", RoleType.LEARNER))

    assert client.get(check_url(challenge)).status_code == 403


def test_visitors_are_refused(client, challenge):
    assert client.get(check_url(challenge)).status_code == 401


def test_unknown_challenge_is_not_found(client, author, challenge):
    sign_in(client, author)

    assert client.get("/api/instructor/challenges/99999/reference-check").status_code == 404


def test_edit_page_offers_the_check(client, author, challenge):
    sign_in(client, author)

    html = client.get(f"/instructor/challenges/{challenge.id}/edit").get_data(as_text=True)

    assert 'id="reference-check-button"' in html
    assert f"/api/instructor/challenges/{challenge.id}/reference-check" in html