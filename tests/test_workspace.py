"""
Tests for saved code (FR05), cleaning pasted code, and protecting attempted
challenges from deletion.
"""

import json
import re

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import Challenge, LearnerProfile, Person, RoleType, SavedCode, UserAccount
from app.services.challenges import (
    ChallengeError,
    add_test_case,
    create_challenge,
    create_topic,
    delete_challenge,
    publish,
    unpublish,
)
from app.services.grading import MAX_CODE_LENGTH, grade_submission
from app.services.workspace import WorkspaceError, get_saved_code, save_code


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


def count_rows(model):
    return db.session.scalar(select(func.count()).select_from(model))


def editor_config(html):
    match = re.search(r'<script type="application/json" id="challenge-data">(.*?)</script>', html, re.S)
    return json.loads(match.group(1))


@pytest.fixture
def topic(app):
    return create_topic("Strings", sort_order=1)


@pytest.fixture
def challenge(topic):
    challenge = create_challenge(
        None, "Reverse a String", "Print the input reversed.", topic, "beginner",
        starter_code="text = input()",
        reference_solution="print(input()[::-1])",
    )
    add_test_case(challenge, "abc", "cba", is_hidden=False)
    add_test_case(challenge, "hello", "olleh", is_hidden=True)
    add_test_case(challenge, "a", "a", is_hidden=True)
    publish(challenge)
    return challenge


# ---------------------------------------------------------------------------
# Saved code
# ---------------------------------------------------------------------------

def test_saving_replaces_the_previous_copy(challenge):
    learner = make_learner()

    save_code(learner, challenge, "first")
    save_code(learner, challenge, "second")

    assert get_saved_code(learner, challenge) == "second"
    assert count_rows(SavedCode) == 1


def test_saved_code_belongs_to_one_learner(challenge):
    ada = make_learner("ada@example.com")
    grace = make_learner("grace@example.com")

    save_code(ada, challenge, "ada's code")

    assert get_saved_code(grace, challenge) is None


def test_overlong_code_is_rejected(challenge):
    with pytest.raises(WorkspaceError):
        save_code(make_learner(), challenge, "x" * (MAX_CODE_LENGTH + 1))


def test_api_saves_code_with_normal_line_endings(client, challenge):
    learner = make_learner()
    sign_in(client, learner)

    response = client.put(
        f"/api/challenges/{challenge.slug}/code", json={"code": "a = 1\r\nprint(a)"}
    )

    assert response.status_code == 200
    assert get_saved_code(learner, challenge) == "a = 1\nprint(a)"


def test_api_save_requires_login(client, challenge):
    response = client.put(f"/api/challenges/{challenge.slug}/code", json={"code": "x"})

    assert response.status_code == 401


def test_page_opens_with_saved_code(client, challenge):
    learner = make_learner()
    save_code(learner, challenge, "my work in progress")
    sign_in(client, learner)

    config = editor_config(client.get(f"/challenges/{challenge.slug}").get_data(as_text=True))

    assert config["initialCode"] == "my work in progress"
    assert config["starterCode"] == "text = input()"


def test_page_opens_with_starter_code_when_nothing_is_saved(client, challenge):
    sign_in(client, make_learner())

    config = editor_config(client.get(f"/challenges/{challenge.slug}").get_data(as_text=True))

    assert config["initialCode"] == "text = input()"


# ---------------------------------------------------------------------------
# Cleaning pasted code
# ---------------------------------------------------------------------------

def test_indentation_shared_by_every_line_is_removed(topic):
    challenge = create_challenge(
        None, "Pasted", "Pasted from a document.", topic, "beginner",
        starter_code="\n    text = input()\n    print(text)\n",
    )

    assert challenge.starter_code == "text = input()\nprint(text)"


def test_relative_indentation_is_kept(topic):
    challenge = create_challenge(
        None, "Loop", "A loop.", topic, "beginner",
        reference_solution="  for letter in input():\n      print(letter)",
    )

    assert challenge.reference_solution == "for letter in input():\n    print(letter)"


def test_expected_outputs_keep_their_leading_spaces(challenge):
    test_case = add_test_case(challenge, "x", "   indented answer", is_hidden=False)

    assert test_case.expected_output == "   indented answer"


# ---------------------------------------------------------------------------
# Deleting challenges
# ---------------------------------------------------------------------------

def test_attempted_challenge_cannot_be_deleted(challenge):
    learner = make_learner()
    results = [{"test_id": test.id, "output": "wrong"} for test in challenge.test_cases]
    grade_submission(learner, challenge, "print('wrong')", results)
    unpublish(challenge)

    with pytest.raises(ChallengeError):
        delete_challenge(challenge)

    assert count_rows(Challenge) == 1


def test_deleting_an_unattempted_challenge_removes_saved_code(challenge):
    save_code(make_learner(), challenge, "some work")
    unpublish(challenge)

    delete_challenge(challenge)

    assert count_rows(Challenge) == 0
    assert count_rows(SavedCode) == 0