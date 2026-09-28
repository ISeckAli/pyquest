"""
Tests for the learner dashboard (spec FR14 with FR07 to FR10).
"""

import pytest

from app.extensions import db
from app.models import LearnerBadge, LearnerProfile, Person, RoleType, UserAccount


def make_learner(xp=0, level=1):
    person = Person(display_name="Ada", email="ada@example.com")
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    profile = LearnerProfile(person=person, total_xp=xp, level=level, current_streak=0, longest_streak=0)
    db.session.add_all([person, account, profile])
    db.session.commit()
    return account


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


def dashboard(client):
    return client.get("/dashboard").get_data(as_text=True)


def test_dashboard_shows_level_progress(client):
    sign_in(client, make_learner(xp=150, level=2))

    html = dashboard(client)

    # Level 2 runs from 100 to 300 XP, so 150 XP is 25% of the way.
    assert "Progress to level 3" in html
    assert 'aria-valuenow="25"' in html
    assert "150 XP to go" in html


def test_visiting_creates_todays_missions(client):
    sign_in(client, make_learner())

    assert "Solve any challenge" in dashboard(client)


def test_earned_and_locked_badges_are_both_shown(client):
    learner = make_learner()
    db.session.add(LearnerBadge(party_id=learner.party_id, badge_code="first-solve"))
    db.session.commit()
    sign_in(client, learner)

    html = dashboard(client)

    assert "First Solve" in html
    assert "Earned" in html
    assert "Still to earn" in html
    assert "Week Streak" in html


def test_new_learner_sees_a_zero_streak(client):
    sign_in(client, make_learner())

    assert "0 days" in dashboard(client)