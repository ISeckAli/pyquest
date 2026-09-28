"""
Tests for daily missions (spec FR10) and the Mission Streak badge.

Most tests add specific missions directly, so each checks one rule without
depending on the random daily pick; separate tests cover the pick itself.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import (
    ContentSource,
    DailyMission,
    Hint,
    LearnerProfile,
    Person,
    RoleType,
    UserAccount,
)
from app.services.challenges import add_test_case, create_challenge, create_topic, publish
from app.services.grading import grade_submission
from app.services.missions import (
    MISSIONS_PER_DAY,
    SOLVE_ANY,
    SOLVE_DIFFICULTY,
    SOLVE_TWO_IN_TOPIC,
    SOLVE_UNASSISTED,
    describe,
    todays_missions,
)

# Noon in Toronto (16:00 UTC), 28 September 2026.
NOW = datetime(2026, 9, 28, 16, 0, tzinfo=UTC)
TODAY = date(2026, 9, 28)


def make_learner():
    person = Person(display_name="learner", email="learner@example.com", timezone="America/Toronto")
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    profile = LearnerProfile(person=person, total_xp=0, level=1, current_streak=0, longest_streak=0)
    db.session.add_all([person, account, profile])
    db.session.commit()
    return account


def make_challenge(topic, title, difficulty="beginner"):
    challenge = create_challenge(
        None, title, f"Solve {title}.", topic, difficulty, reference_solution="print(input())"
    )
    add_test_case(challenge, "a", "a", is_hidden=False)
    add_test_case(challenge, "b", "b", is_hidden=True)
    add_test_case(challenge, "c", "c", is_hidden=True)
    publish(challenge)
    return challenge


def solve(learner, challenge, now=NOW):
    results = [{"test_id": test.id, "output": test.expected_output} for test in challenge.test_cases]
    return grade_submission(learner, challenge, "print(input())", results, now=now)[1]


def add_mission(learner, template, target=None, goal=1, day=TODAY, completed=False):
    mission = DailyMission(
        party_id=learner.party_id,
        mission_date=day,
        template=template,
        target=target,
        goal=goal,
        progress=goal if completed else 0,
        bonus_xp=15,
        completed_at=datetime.combine(day, datetime.min.time(), tzinfo=UTC) if completed else None,
    )
    db.session.add(mission)
    db.session.commit()
    return mission


@pytest.fixture
def learner(app):
    return make_learner()


@pytest.fixture
def topic(app):
    return create_topic("Strings", sort_order=1)


# ---------------------------------------------------------------------------
# The daily pick
# ---------------------------------------------------------------------------

def test_three_missions_are_created_once_per_day(learner, topic):
    make_challenge(topic, "One")
    make_challenge(topic, "Two")

    first = todays_missions(learner, NOW)
    again = todays_missions(learner, NOW + timedelta(hours=3))

    assert len(first) == MISSIONS_PER_DAY
    assert first[0].template == SOLVE_ANY
    assert [mission.id for mission in again] == [mission.id for mission in first]


def test_the_daily_pick_is_repeatable(learner, topic):
    make_challenge(topic, "One")
    make_challenge(topic, "Two")
    first_pick = [(m.template, m.target) for m in todays_missions(learner, NOW)]

    for mission in db.session.scalars(select(DailyMission)).all():
        db.session.delete(mission)
    db.session.commit()

    assert [(m.template, m.target) for m in todays_missions(learner, NOW)] == first_pick


def test_a_new_day_brings_new_missions(learner, topic):
    make_challenge(topic, "One")
    todays_missions(learner, NOW)

    todays_missions(learner, NOW + timedelta(days=1))

    assert db.session.query(DailyMission).count() == 2 * MISSIONS_PER_DAY


# ---------------------------------------------------------------------------
# Progress and bonus XP
# ---------------------------------------------------------------------------

def test_completing_a_mission_awards_bonus_xp(learner, topic):
    add_mission(learner, SOLVE_ANY)

    feedback = solve(learner, make_challenge(topic, "One"))

    assert feedback["mission_xp"] == 15
    assert feedback["total_xp"] == 10 + 15
    assert feedback["completed_missions"][0]["title"] == "Solve any challenge"


def test_resolving_a_solved_challenge_does_not_advance_missions(learner, topic):
    challenge = make_challenge(topic, "One")
    solve(learner, challenge)
    tomorrow = add_mission(learner, SOLVE_ANY, day=TODAY + timedelta(days=1))

    feedback = solve(learner, challenge, now=NOW + timedelta(days=1))

    assert feedback["mission_xp"] == 0
    assert tomorrow.progress == 0


def test_unassisted_mission_needs_a_solve_without_ai_hints(learner, topic):
    challenge = make_challenge(topic, "One")
    mission = add_mission(learner, SOLVE_UNASSISTED)
    db.session.add(
        Hint(party_id=learner.party_id, challenge_id=challenge.id, level=1,
             text="A hint.", source=ContentSource.AI)
    )
    db.session.commit()

    solve(learner, challenge)

    assert not mission.is_completed


def test_topic_mission_needs_two_solves_in_that_topic(learner, topic):
    mission = add_mission(learner, SOLVE_TWO_IN_TOPIC, target="strings", goal=2)

    solve(learner, make_challenge(topic, "One"))
    assert mission.progress == 1 and not mission.is_completed

    solve(learner, make_challenge(topic, "Two"))
    assert mission.is_completed


def test_yesterdays_missions_have_expired(learner, topic):
    yesterday = add_mission(learner, SOLVE_ANY, day=TODAY - timedelta(days=1))

    solve(learner, make_challenge(topic, "One"))

    assert yesterday.progress == 0


def test_mission_titles_name_the_difficulty_and_topic(learner, topic):
    difficulty = add_mission(learner, SOLVE_DIFFICULTY, target="intermediate")
    in_topic = add_mission(learner, SOLVE_TWO_IN_TOPIC, target="strings", goal=2)

    assert describe(difficulty)["title"] == "Solve a Intermediate challenge" or \
        describe(difficulty)["title"] == "Solve an Intermediate challenge"
    assert describe(in_topic)["title"] == "Solve 2 challenges in Strings"


# ---------------------------------------------------------------------------
# Mission Streak badge
# ---------------------------------------------------------------------------

def test_seven_days_of_missions_earn_the_mission_streak_badge(learner, topic):
    for days_ago in range(6, 0, -1):
        add_mission(learner, SOLVE_ANY, day=TODAY - timedelta(days=days_ago), completed=True)

    feedback = solve(learner, make_challenge(topic, "One"))

    assert "mission-streak" in [badge["code"] for badge in feedback["new_badges"]]