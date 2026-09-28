"""
Tests for instructor analytics (spec FR15).
"""

import pytest

from app.extensions import db
from app.models import ContentSource, Hint, Person, RoleType, Submission, SubmissionStatus, UserAccount
from app.services.challenges import create_challenge, create_topic
from app.services.instructor_analytics import challenge_stats


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


def attempt(learner, challenge, passed, error=None):
    db.session.add(
        Submission(
            party_id=learner.party_id, challenge_id=challenge.id, code="x",
            status=SubmissionStatus.PASSED if passed else SubmissionStatus.FAILED,
            passed_count=1 if passed else 0, total_count=1, error_category=error,
        )
    )
    db.session.commit()


@pytest.fixture
def topic(app):
    return create_topic("Strings", sort_order=1)


@pytest.fixture
def author(app):
    return make_account("teach@example.com", RoleType.INSTRUCTOR)


def learners(count):
    return [make_account(f"l{n}@example.com", RoleType.LEARNER) for n in range(count)]


def test_statistics_per_challenge(author, topic):
    challenge = create_challenge(author, "One", "Solve it.", topic, "beginner")
    ada, grace = learners(2)
    attempt(ada, challenge, passed=False, error="NameError")
    attempt(ada, challenge, passed=True)
    attempt(grace, challenge, passed=False, error="NameError")
    db.session.add(Hint(party_id=grace.party_id, challenge_id=challenge.id, level=1,
                        text="A hint.", source=ContentSource.AI))
    db.session.commit()

    row = challenge_stats(author)[0]

    assert row["attempts"] == 3
    assert row["learners"] == 2
    assert row["solvers"] == 1
    assert row["solve_rate"] == 50
    assert row["pass_rate"] == 33
    assert row["top_error"] == "NameError"
    assert row["ai_hints"] == 1


def test_hard_challenges_need_attention_only_with_enough_learners(author, topic):
    hard = create_challenge(author, "Hard", "Solve it.", topic, "beginner")
    early = create_challenge(author, "Early", "Solve it.", topic, "beginner")
    for learner in learners(3):
        attempt(learner, hard, passed=False)
    attempt(make_account("solo@example.com", RoleType.LEARNER), early, passed=False)

    flags = {row["title"]: row["needs_attention"] for row in challenge_stats(author)}

    assert flags == {"Hard": True, "Early": False}


def test_instructors_see_their_own_and_admins_see_all(author, topic):
    create_challenge(author, "Mine", "Solve it.", topic, "beginner")
    create_challenge(make_account("other@example.com", RoleType.INSTRUCTOR),
                     "Theirs", "Solve it.", topic, "beginner")
    admin = make_account("admin@example.com", RoleType.SYSTEM_ADMINISTRATOR)

    assert [row["title"] for row in challenge_stats(author)] == ["Mine"]
    assert {row["title"] for row in challenge_stats(admin)} == {"Mine", "Theirs"}


def test_analytics_page_is_for_staff_only(client, author, topic):
    create_challenge(author, "One", "Solve it.", topic, "beginner")

    sign_in(client, make_account("learner@example.com", RoleType.LEARNER))
    assert client.get("/instructor/analytics").status_code == 403

    sign_in(client, author)
    response = client.get("/instructor/analytics")
    assert response.status_code == 200
    assert "One" in response.get_data(as_text=True)


def test_challenge_list_links_to_analytics(client, author):
    sign_in(client, author)

    html = client.get("/instructor/challenges").get_data(as_text=True)

    assert 'href="/instructor/analytics"' in html