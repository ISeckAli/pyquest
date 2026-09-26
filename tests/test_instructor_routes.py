"""
Tests for the instructor pages (spec FR12, FR03): access control, writing
and editing challenges, test cases, and the publishing lifecycle.
"""

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import Challenge, ChallengeStatus, Person, RoleType, TestCase, UserAccount
from app.services.challenges import (
    add_test_case,
    create_challenge,
    create_topic,
    publish,
    set_fallback_hints,
)

PASSWORD = "violet-harbour-42"


def make_account(email, *roles, password=None):
    """Create an account. Without a password, a placeholder hash is used,
    which avoids slow password hashing in tests that never log in."""
    person = Person(display_name=email.split("@")[0], email=email)
    for role in roles:
        person.add_role(role)
    account = UserAccount(party=person)
    if password:
        account.set_password(password)
    else:
        account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account])
    db.session.commit()
    return account


def sign_in(client, account):
    """Sign an account in directly, skipping the login form.

    Flask-Login keeps the signed-in account's id in the session under
    "_user_id". Setting it here keeps these tests fast; the login form
    itself is covered by test_auth_routes.py.
    """
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


def count_rows(model):
    return db.session.scalar(select(func.count()).select_from(model))


def stored(challenge_id):
    db.session.expire_all()
    return db.session.get(Challenge, challenge_id)


@pytest.fixture
def topic(app):
    return create_topic("Strings", sort_order=1)


@pytest.fixture
def instructor(client, topic):
    """A signed-in instructor who is not a learner."""
    account = make_account("teach@example.com", RoleType.INSTRUCTOR)
    sign_in(client, account)
    return account


def draft_by(account, topic, title="Reverse a String"):
    return create_challenge(
        account, title, "Print the input reversed.", topic, "beginner",
        reference_solution="print(input()[::-1])",
    )


def add_required_tests(challenge):
    add_test_case(challenge, "abc", "cba", is_hidden=False)
    add_test_case(challenge, "hello", "olleh", is_hidden=True)
    add_test_case(challenge, "a", "a", is_hidden=True)


def challenge_form(topic, **changes):
    data = {
        "title": "Reverse a String",
        "topic_id": str(topic.id),
        "difficulty": "beginner",
        "xp_value": "",
        "description": "Print the input reversed.",
        "starter_code": "text = input()",
        "reference_solution": "print(input()[::-1])",
        "hint_1": "Think about slicing.",
        "hint_2": "",
        "hint_3": "",
    }
    data.update(changes)
    return data


def edit_url(challenge):
    return f"/instructor/challenges/{challenge.id}"


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def test_visitors_are_sent_to_login(client):
    response = client.get("/instructor/challenges")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_learners_are_forbidden(client, app):
    sign_in(client, make_account("learner@example.com", RoleType.LEARNER))

    assert client.get("/instructor/challenges").status_code == 403


def test_other_instructors_cannot_touch_a_challenge(client, instructor, topic):
    theirs = draft_by(make_account("other@example.com", RoleType.INSTRUCTOR), topic)

    assert client.get(edit_url(theirs) + "/edit").status_code == 403
    assert client.post(edit_url(theirs) + "/publish").status_code == 403


def test_administrators_can_manage_any_challenge(client, topic):
    challenge = draft_by(make_account("teach@example.com", RoleType.INSTRUCTOR), topic)
    sign_in(client, make_account("admin@example.com", RoleType.SYSTEM_ADMINISTRATOR))

    assert client.get(edit_url(challenge) + "/edit").status_code == 200


def test_list_shows_only_the_instructors_own_challenges(client, instructor, topic):
    draft_by(instructor, topic, title="Mine")
    draft_by(make_account("other@example.com", RoleType.INSTRUCTOR), topic, title="Theirs")

    html = client.get("/instructor/challenges").get_data(as_text=True)

    assert "Mine" in html
    assert "Theirs" not in html


# ---------------------------------------------------------------------------
# Creating and editing
# ---------------------------------------------------------------------------

def test_creating_a_challenge_saves_a_draft_with_hints(client, instructor, topic):
    response = client.post("/instructor/challenges/new", data=challenge_form(topic))

    challenge = db.session.scalars(select(Challenge)).one()
    assert response.headers["Location"] == edit_url(challenge) + "/edit"
    assert challenge.status == ChallengeStatus.DRAFT
    assert challenge.xp_value == 10
    assert challenge.author_id == instructor.party_id
    assert [hint.text for hint in challenge.fallback_hints] == ["Think about slicing."]


def test_invalid_challenge_form_shows_errors_and_saves_nothing(client, instructor, topic):
    response = client.post("/instructor/challenges/new", data=challenge_form(topic, title="ab"))

    assert response.status_code == 200
    assert b"Title must be" in response.data
    assert count_rows(Challenge) == 0


def test_edit_page_is_prefilled(client, instructor, topic):
    challenge = draft_by(instructor, topic)
    set_fallback_hints(challenge, ["Think about slicing."])

    html = client.get(edit_url(challenge) + "/edit").get_data(as_text=True)

    assert 'value="Reverse a String"' in html
    assert "Think about slicing." in html


def test_saving_edits_updates_the_challenge(client, instructor, topic):
    challenge = draft_by(instructor, topic)

    response = client.post(
        edit_url(challenge) + "/edit", data=challenge_form(topic, title="Reverse Words")
    )

    assert response.status_code == 302
    assert stored(challenge.id).title == "Reverse Words"


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_adding_a_hidden_test_case(client, instructor, topic):
    challenge = draft_by(instructor, topic)

    client.post(
        edit_url(challenge) + "/tests",
        data={
            "test-input_data": "abc",
            "test-expected_output": "cba",
            "test-is_hidden": "y",
        },
    )

    assert len(stored(challenge.id).hidden_tests) == 1


def test_removing_a_test_case(client, instructor, topic):
    challenge = draft_by(instructor, topic)
    test_case = add_test_case(challenge, "abc", "cba", is_hidden=False)

    client.post(f"{edit_url(challenge)}/tests/{test_case.id}/delete")

    assert count_rows(TestCase) == 0


def test_a_test_cannot_be_removed_through_another_challenge(client, instructor, topic):
    """Changing the ids in the address must not reach another challenge's tests."""
    first = draft_by(instructor, topic, title="First")
    second = draft_by(instructor, topic, title="Second")
    test_case = add_test_case(second, "abc", "cba", is_hidden=False)

    response = client.post(f"{edit_url(first)}/tests/{test_case.id}/delete")

    assert response.status_code == 404
    assert count_rows(TestCase) == 1


# ---------------------------------------------------------------------------
# Publishing lifecycle
# ---------------------------------------------------------------------------

def test_incomplete_challenge_is_refused_with_reasons(client, instructor, topic):
    challenge = draft_by(instructor, topic)

    response = client.post(edit_url(challenge) + "/publish", follow_redirects=True)

    assert b"not ready to publish" in response.data
    assert b"Add at least" in response.data
    assert stored(challenge.id).status == ChallengeStatus.DRAFT


def test_publishing_a_ready_challenge_makes_it_public(client, instructor, topic):
    challenge = draft_by(instructor, topic)
    add_required_tests(challenge)

    client.post(edit_url(challenge) + "/publish")

    assert stored(challenge.id).status == ChallengeStatus.PUBLISHED
    assert b"Reverse a String" in client.get("/challenges").data


def test_published_challenge_must_be_unpublished_before_deleting(client, instructor, topic):
    challenge = draft_by(instructor, topic)
    add_required_tests(challenge)
    publish(challenge)

    client.post(edit_url(challenge) + "/delete")
    assert count_rows(Challenge) == 1

    client.post(edit_url(challenge) + "/unpublish")
    response = client.post(edit_url(challenge) + "/delete")

    assert response.headers["Location"] == "/instructor/challenges"
    assert count_rows(Challenge) == 0


def test_preview_shows_a_draft_that_learners_cannot_see(client, instructor, topic):
    challenge = draft_by(instructor, topic)

    preview = client.get(edit_url(challenge) + "/preview")

    assert preview.status_code == 200
    assert b"Preview:" in preview.data
    assert client.get(f"/challenges/{challenge.slug}").status_code == 404


# ---------------------------------------------------------------------------
# Navigation for staff
# ---------------------------------------------------------------------------

def test_header_shows_instructor_link_and_hides_dashboard_for_staff(client, instructor):
    html = client.get("/").get_data(as_text=True)

    assert 'href="/instructor/challenges"' in html
    assert 'href="/dashboard"' not in html


def test_staff_who_are_not_learners_land_on_instructor_page(client, app):
    make_account("teach@example.com", RoleType.INSTRUCTOR, password=PASSWORD)

    response = client.post("/login", data={"email": "teach@example.com", "password": PASSWORD})

    assert response.headers["Location"] == "/instructor/challenges"