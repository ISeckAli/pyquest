"""
Tests for Coach progress summaries (spec PR-C5). AI replies come from the
fake provider.
"""

from datetime import UTC, datetime

import pytest

from app.extensions import db
from app.models import (
    ContentSource,
    LearnerProfile,
    Person,
    RoleType,
    Submission,
    SubmissionStatus,
    UserAccount,
)
from app.services.ai_service import get_provider
from app.services.challenges import create_challenge, create_topic
from app.services.coach import CoachError
from app.services.coach_summary import create_summary

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


@pytest.fixture
def learner(app):
    person = Person(display_name="Ada Lovelace", email="ada@example.com")
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    profile = LearnerProfile(person=person, total_xp=0, level=1, current_streak=0, longest_streak=0)
    db.session.add_all([person, account, profile])
    db.session.commit()
    return account


@pytest.fixture
def with_submissions(learner):
    topic = create_topic("Strings", sort_order=1)
    challenge = create_challenge(None, "One", "Solve it.", topic, "beginner")
    for passed, error in [(True, None), (False, "NameError")]:
        db.session.add(
            Submission(
                party_id=learner.party_id, challenge_id=challenge.id, code="x",
                status=SubmissionStatus.PASSED if passed else SubmissionStatus.FAILED,
                passed_count=1, total_count=1, error_category=error, submitted_at=NOW,
            )
        )
    db.session.commit()
    return learner


def test_summary_uses_statistics_but_no_personal_details(with_submissions):
    summary = create_summary(with_submissions, NOW)
    prompt = get_provider().calls[0]["prompt"]

    assert summary.source == ContentSource.AI
    assert "pass rate 50%" in prompt
    assert "NameError" in prompt
    assert "Ada" not in prompt
    assert "ada@example.com" not in prompt


def test_one_summary_per_day(with_submissions):
    first = create_summary(with_submissions, NOW)
    second = create_summary(with_submissions, NOW)

    assert first.id == second.id
    assert len(get_provider().calls) == 1


def test_built_in_summary_uses_the_same_statistics(with_submissions):
    get_provider().fail = True

    summary = create_summary(with_submissions, NOW)

    assert summary.source == ContentSource.FALLBACK
    assert "50% pass rate" in summary.content
    assert "NameError" in summary.content


def test_no_summary_before_any_submissions(learner):
    with pytest.raises(CoachError):
        create_summary(learner, NOW)


def test_dashboard_button_creates_and_shows_the_summary(client, with_submissions):
    sign_in(client, with_submissions)

    response = client.post("/dashboard/summary", follow_redirects=True)
    html = response.get_data(as_text=True)

    assert "AI Coach · AI-generated" in html
    assert get_provider().DEFAULT_REPLY in html