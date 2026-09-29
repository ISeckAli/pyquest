"""
Tests for guest mode (spec PR-A3): starting a guest session, staying off the
leaderboard, converting to a real account, the chat allowance, and cleanup.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    LearnerProfile,
    Person,
    RoleType,
    Submission,
    SubmissionStatus,
    UserAccount,
)
from app.services.challenges import add_test_case, create_challenge, create_topic, publish
from app.services.guest import GUEST_CHAT_LIMIT, create_guest, delete_expired_guests
from app.services.leaderboard import standings

PASSWORD = "violet-harbour-42"


def count(model):
    return db.session.scalar(select(func.count()).select_from(model))


def the_account():
    return db.session.scalars(select(UserAccount)).one()


def sign_up_data(email="ada@example.com"):
    return {
        "display_name": "Ada",
        "email": email,
        "password": PASSWORD,
        "confirm_password": PASSWORD,
    }


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


def test_try_as_guest_signs_in_a_hidden_guest_learner(client):
    response = client.post("/guest")

    account = the_account()
    assert response.headers["Location"] == "/challenges"
    assert account.is_guest
    assert account.has_role(RoleType.LEARNER)
    assert account.party.leaderboard_visible is False
    assert client.get("/dashboard").status_code == 200


def test_guests_never_appear_on_the_leaderboard(app):
    guest = create_guest()
    guest.party.learner_profile.total_xp = 500
    db.session.commit()

    assert standings() == []


def test_signing_up_as_a_guest_keeps_their_progress(client):
    client.post("/guest")
    account = the_account()
    account.party.learner_profile.total_xp = 25
    db.session.commit()

    response = client.post("/register", data=sign_up_data())

    db.session.expire_all()
    account = the_account()
    assert response.headers["Location"] == "/dashboard"
    assert count(Person) == 1
    assert not account.is_guest
    assert account.party.email == "ada@example.com"
    assert account.party.learner_profile.total_xp == 25
    assert account.check_password(PASSWORD)


def test_a_guest_cannot_take_an_existing_email(client):
    existing = Person(display_name="Taken", email="ada@example.com")
    db.session.add(existing)
    db.session.commit()
    client.post("/guest")

    response = client.post("/register", data=sign_up_data())

    assert b"already exists" in response.data
    assert db.session.scalars(select(Person).where(Person.is_guest.is_(True))).one()


def test_guest_chat_is_limited(client, challenge):
    client.post("/guest")
    url = f"/api/challenges/{challenge.slug}/chat"

    for _ in range(GUEST_CHAT_LIMIT):
        assert client.post(url, json={"message": "Help?", "code": ""}).status_code == 200
    response = client.post(url, json={"message": "One more?", "code": ""})

    assert response.status_code == 429
    assert "Create a free account" in response.get_json()["error"]


def test_guests_are_sent_from_settings_to_sign_up(client):
    client.post("/guest")

    response = client.get("/settings")

    assert response.headers["Location"] == "/register"


def test_expired_guests_are_deleted_with_their_data(app, challenge):
    now = datetime.now(UTC)
    old_guest = create_guest()
    old_guest.party.created_at = now - timedelta(days=8)
    db.session.add(
        Submission(
            party_id=old_guest.party_id, challenge_id=challenge.id, code="x",
            status=SubmissionStatus.PASSED, passed_count=3, total_count=3,
        )
    )
    create_guest()  # recent, kept
    real = Person(display_name="Real", email="real@example.com")
    real.created_at = now - timedelta(days=30)
    db.session.add(real)
    db.session.commit()

    deleted = delete_expired_guests(now)

    assert deleted == 1
    assert count(Person) == 2
    assert count(Submission) == 0
    assert count(LearnerProfile) == 1


def test_cleanup_command_reports_what_it_deleted(app):
    result = app.test_cli_runner().invoke(args=["cleanup-guests"])

    assert result.exit_code == 0
    assert "Deleted 0 expired guest accounts" in result.output