"""
Tests for adaptive recommendations (Part 15): the four rules, and where
recommendations appear (after solving, the dashboard, the Coach summary).
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, Submission, SubmissionStatus, UserAccount
from app.services.ai_service import get_provider
from app.services.challenges import add_test_case, create_challenge, create_topic, publish
from app.services.coach_summary import create_summary
from app.services.recommendations import STRUGGLE_FAILURES, recommendations

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def make_challenge(title, topic, difficulty):
    challenge = create_challenge(
        None, title, "Solve it.", topic, difficulty, reference_solution="print(input())"
    )
    add_test_case(challenge, "a", "a", is_hidden=False)
    add_test_case(challenge, "b", "b", is_hidden=True)
    add_test_case(challenge, "c", "c", is_hidden=True)
    publish(challenge)
    return challenge


@pytest.fixture
def course(app):
    """Strings (Beginner One, Beginner Two, Intermediate) then Loops (Beginner)."""
    strings = create_topic("Strings", sort_order=1)
    loops = create_topic("Loops", sort_order=2)
    return {
        "s1": make_challenge("Strings One", strings, "beginner"),
        "s2": make_challenge("Strings Two", strings, "beginner"),
        "s_int": make_challenge("Strings Hard", strings, "intermediate"),
        "l1": make_challenge("Loops One", loops, "beginner"),
    }


@pytest.fixture
def learner(app):
    person = Person(display_name="Ada", email="ada@example.com")
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account, LearnerProfile(person=person)])
    db.session.commit()
    return account


def attempt(learner, challenge, passed, minutes_ago=0):
    db.session.add(
        Submission(
            party_id=learner.party_id, challenge_id=challenge.id, code="x",
            status=SubmissionStatus.PASSED if passed else SubmissionStatus.FAILED,
            passed_count=3 if passed else 0, total_count=3,
            submitted_at=NOW - timedelta(minutes=minutes_ago),
        )
    )
    db.session.commit()


def titles(learner):
    return [item.challenge.title for item in recommendations(learner)]


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------

def test_a_new_learner_follows_the_learning_path(course, learner):
    picks = recommendations(learner)

    assert [item.challenge.title for item in picks] == ["Strings One", "Strings Two", "Strings Hard"]
    assert picks[0].reason == "Next on your learning path."


def test_an_unfinished_challenge_comes_first(course, learner):
    attempt(learner, course["s2"], passed=False)

    first = recommendations(learner)[0]

    assert first.challenge.title == "Strings Two"
    assert first.reason == "Pick up where you left off."


def test_struggling_leads_to_easier_practice_in_the_same_topic(course, learner):
    for minutes in range(STRUGGLE_FAILURES):
        attempt(learner, course["s_int"], passed=False, minutes_ago=minutes)

    first = recommendations(learner)[0]

    assert first.challenge.title == "Strings One"
    assert "then return to Strings Hard" in first.reason


def test_struggling_with_no_easier_option_suggests_a_hint(course, learner):
    attempt(learner, course["s1"], passed=True)
    attempt(learner, course["s2"], passed=True)
    for minutes in range(STRUGGLE_FAILURES):
        attempt(learner, course["s_int"], passed=False, minutes_ago=minutes)

    first = recommendations(learner)[0]

    assert first.challenge.title == "Strings Hard"
    assert "hint" in first.reason


def test_mastering_a_topics_beginners_steps_up(course, learner):
    attempt(learner, course["s1"], passed=True)
    attempt(learner, course["s2"], passed=True)

    first = recommendations(learner)[0]

    assert first.challenge.title == "Strings Hard"
    assert "every Beginner challenge in Strings" in first.reason


def test_solved_challenges_are_never_recommended(course, learner):
    for challenge in course.values():
        attempt(learner, challenge, passed=True)

    assert recommendations(learner) == []


# ---------------------------------------------------------------------------
# Where recommendations appear
# ---------------------------------------------------------------------------

def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


def test_a_solve_returns_the_recommended_next_challenge(client, course, learner):
    sign_in(client, learner)
    challenge = course["s1"]
    results = [{"test_id": t.id, "output": t.expected_output} for t in challenge.test_cases]

    feedback = client.post(
        f"/api/challenges/{challenge.slug}/submissions", json={"code": "print(input())", "results": results}
    ).get_json()

    assert feedback["next"]["title"] == "Strings Two"
    assert feedback["next"]["reason"] == "Next on your learning path."


def test_the_dashboard_shows_recommendations(client, course, learner):
    sign_in(client, learner)

    html = client.get("/dashboard").get_data(as_text=True)

    assert "Recommended for you" in html
    assert f'href="/challenges/{course["s1"].slug}"' in html


def test_the_coach_summary_knows_the_recommended_challenge(course, learner):
    attempt(learner, course["s1"], passed=True)

    create_summary(learner, NOW)

    assert "Recommended next challenge: Strings Two" in get_provider().calls[-1]["prompt"]