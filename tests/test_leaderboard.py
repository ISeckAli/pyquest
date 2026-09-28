"""
Tests for the leaderboard (spec FR09): ranking, privacy, the weekly board,
and the page itself.
"""

from datetime import UTC, date, datetime

import pytest

from app.extensions import db
from app.models import (
    DailyMission,
    LearnerProfile,
    Person,
    RoleType,
    Submission,
    SubmissionStatus,
    UserAccount,
)
from app.services.challenges import create_challenge, create_topic
from app.services.leaderboard import THIS_WEEK, leaderboard, standings, week_start

# Wednesday 30 September 2026; the week began Monday 28 September.
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def make_learner(name, xp, visible=True, active=True):
    person = Person(display_name=name, email=f"{name.lower()}@example.com")
    person.leaderboard_visible = visible
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person, is_active=active)
    account.password_hash = "not-used-in-these-tests"
    profile = LearnerProfile(person=person, total_xp=xp, level=1, current_streak=0, longest_streak=0)
    db.session.add_all([person, account, profile])
    db.session.commit()
    return account


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


@pytest.fixture
def challenge(app):
    topic = create_topic("Strings", sort_order=1)
    return create_challenge(None, "One", "Solve it.", topic, "beginner")


def add_xp(account, challenge, xp, when):
    """Record XP earned at a given time, as a passing submission would."""
    db.session.add(
        Submission(
            party_id=account.party_id, challenge_id=challenge.id, code="x",
            status=SubmissionStatus.PASSED, passed_count=1, total_count=1,
            xp_awarded=xp, submitted_at=when,
        )
    )
    db.session.commit()


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def test_learners_are_ranked_by_xp_and_ties_share_a_rank(app):
    make_learner("Ada", 300)
    make_learner("Grace", 200)
    make_learner("Alan", 200)
    make_learner("Linus", 50)

    result = [(s.display_name, s.rank) for s in standings()]

    assert result == [("Ada", 1), ("Alan", 2), ("Grace", 2), ("Linus", 4)]


def test_hidden_deactivated_and_zero_xp_learners_are_left_out(app):
    make_learner("Shown", 100)
    make_learner("Hidden", 500, visible=False)
    make_learner("Gone", 400, active=False)
    make_learner("New", 0)

    assert [s.display_name for s in standings()] == ["Shown"]


def test_week_starts_on_monday_utc():
    assert week_start(NOW) == datetime(2026, 9, 28, 0, 0, tzinfo=UTC)


def test_weekly_board_counts_only_this_weeks_xp_and_missions(app, challenge):
    ada = make_learner("Ada", 1000)
    grace = make_learner("Grace", 50)
    add_xp(ada, challenge, 10, datetime(2026, 9, 27, 23, 0, tzinfo=UTC))  # last week
    add_xp(grace, challenge, 25, datetime(2026, 9, 29, 9, 0, tzinfo=UTC))
    db.session.add(
        DailyMission(
            party_id=grace.party_id, mission_date=date(2026, 9, 29), template="solve-any",
            goal=1, progress=1, bonus_xp=15,
            completed_at=datetime(2026, 9, 29, 9, 0, tzinfo=UTC),
        )
    )
    db.session.commit()

    weekly = standings(THIS_WEEK, now=NOW)

    assert [(s.display_name, s.xp) for s in weekly] == [("Grace", 40)]


def test_viewer_below_the_top_sees_their_own_rank(app):
    make_learner("Ada", 300)
    make_learner("Grace", 200)
    linus = make_learner("Linus", 50)

    top, mine = leaderboard(viewer=linus, limit=2)

    assert [s.display_name for s in top] == ["Ada", "Grace"]
    assert mine.rank == 3


def test_viewer_in_the_top_gets_no_separate_rank(app):
    ada = make_learner("Ada", 300)

    _, mine = leaderboard(viewer=ada)

    assert mine is None


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def test_leaderboard_page_is_public_and_shows_no_emails(client):
    make_learner("Ada", 300)

    html = client.get("/leaderboard").get_data(as_text=True)

    assert "Ada" in html
    assert "ada@example.com" not in html


def test_own_row_is_marked_and_hidden_learners_are_told(client):
    ada = make_learner("Ada", 300)
    hidden = make_learner("Quiet", 100, visible=False)

    sign_in(client, ada)
    assert "(you)" in client.get("/leaderboard").get_data(as_text=True)

    sign_in(client, hidden)
    assert "You are hidden from the leaderboard" in client.get("/leaderboard").get_data(as_text=True)


def test_unknown_period_falls_back_to_all_time(client):
    make_learner("Ada", 300)

    response = client.get("/leaderboard?period=forever")

    assert response.status_code == 200
    assert "Ada" in response.get_data(as_text=True)