"""
Tests for learner analytics and the dashboard progress charts (spec FR14).
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, Submission, SubmissionStatus, UserAccount
from app.services.analytics import WEEKS_SHOWN, learner_analytics
from app.services.challenges import create_challenge, create_topic, publish, add_test_case

# Wednesday 30 September 2026; the week began Monday 28 September.
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def make_learner():
    person = Person(display_name="Ada", email="ada@example.com")
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    profile = LearnerProfile(person=person, total_xp=0, level=1, current_streak=0, longest_streak=0)
    db.session.add_all([person, account, profile])
    db.session.commit()
    return account


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


def make_challenge(topic, title, published=True):
    challenge = create_challenge(None, title, "Solve it.", topic, "beginner", reference_solution="print(1)")
    add_test_case(challenge, "", "1", is_hidden=False)
    add_test_case(challenge, "", "1", is_hidden=True)
    add_test_case(challenge, "", "1", is_hidden=True)
    if published:
        publish(challenge)
    return challenge


def add_submission(account, challenge, passed, when=NOW, error=None):
    db.session.add(
        Submission(
            party_id=account.party_id, challenge_id=challenge.id, code="x",
            status=SubmissionStatus.PASSED if passed else SubmissionStatus.FAILED,
            passed_count=1 if passed else 0, total_count=1,
            error_category=error, submitted_at=when,
        )
    )
    db.session.commit()


@pytest.fixture
def learner(app):
    return make_learner()


@pytest.fixture
def topic(app):
    return create_topic("Strings", sort_order=1)


def test_pass_rate_is_grouped_by_week(learner, topic):
    challenge = make_challenge(topic, "One")
    add_submission(learner, challenge, passed=True)
    add_submission(learner, challenge, passed=False)
    add_submission(learner, challenge, passed=False, when=NOW - timedelta(weeks=1))

    accuracy = learner_analytics(learner, NOW)["accuracy"]

    assert len(accuracy["labels"]) == WEEKS_SHOWN
    assert accuracy["attempts"][-1] == 2
    assert accuracy["pass_rate"][-1] == 50
    assert accuracy["pass_rate"][-2] == 0
    assert accuracy["pass_rate"][0] is None  # No attempts that week: a gap, not 0%.


def test_totals_include_every_submission(learner, topic):
    challenge = make_challenge(topic, "One")
    add_submission(learner, challenge, passed=True, when=NOW - timedelta(weeks=20))
    add_submission(learner, challenge, passed=False)

    analytics = learner_analytics(learner, NOW)

    assert analytics["total_submissions"] == 2
    assert analytics["pass_rate"] == 50


def test_errors_are_ranked_most_common_first(learner, topic):
    challenge = make_challenge(topic, "One")
    for error in ["NameError", "IndentationError", "NameError", "TypeError", "NameError", "TypeError"]:
        add_submission(learner, challenge, passed=False, error=error)

    errors = learner_analytics(learner, NOW)["errors"]

    assert [error["name"] for error in errors] == ["NameError", "TypeError", "IndentationError"]
    assert errors[0]["count"] == 3


def test_topic_progress_counts_only_published_challenges(learner, topic):
    solved = make_challenge(topic, "One")
    make_challenge(topic, "Two")
    make_challenge(topic, "Draft", published=False)
    add_submission(learner, solved, passed=True)

    topics = learner_analytics(learner, NOW)["topics"]

    assert topics == [{"name": "Strings", "solved": 1, "total": 2}]


def test_dashboard_shows_charts_only_after_submitting(client, learner, topic):
    sign_in(client, learner)
    assert "Submit a solution to see your progress" in client.get("/dashboard").get_data(as_text=True)

    add_submission(learner, make_challenge(topic, "One"), passed=True)
    html = client.get("/dashboard").get_data(as_text=True)

    assert 'id="accuracy-chart"' in html
    assert 'id="analytics-data"' in html
    assert "Strings: 1 of 1 solved" in html