"""
Tests for streaks and badges (spec FR08, PR-G1). Solves go through the real
grading service with fixed times, so streaks across days are checked
without waiting.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount
from app.services.challenges import add_test_case, create_challenge, create_topic, publish
from app.services.gamification import badge_info, displayed_streak
from app.services.grading import grade_submission

# Noon in Toronto (16:00 UTC), 28 September 2026.
NOW = datetime(2026, 9, 28, 16, 0, tzinfo=UTC)


def make_learner(email="learner@example.com"):
    person = Person(display_name=email.split("@")[0], email=email, timezone="America/Toronto")
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    profile = LearnerProfile(
        person=person, total_xp=0, level=1, current_streak=0, longest_streak=0
    )
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


def badge_codes(feedback):
    return [badge["code"] for badge in feedback["new_badges"]]


@pytest.fixture
def learner(app):
    return make_learner()


@pytest.fixture
def topic(app):
    return create_topic("Strings", sort_order=1)


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------

def test_first_solve_starts_a_streak_and_earns_a_badge(learner, topic):
    feedback = solve(learner, make_challenge(topic, "One"))

    assert feedback["current_streak"] == 1
    assert "first-solve" in badge_codes(feedback)


def test_badges_are_earned_only_once(learner, topic):
    first = make_challenge(topic, "One")
    second = make_challenge(topic, "Two")

    solve(learner, first)
    feedback = solve(learner, second)

    assert "first-solve" not in badge_codes(feedback)


def test_topic_and_beginner_badges_need_every_challenge(learner, topic):
    first = make_challenge(topic, "One")
    second = make_challenge(topic, "Two")

    after_one = badge_codes(solve(learner, first))
    after_two = badge_codes(solve(learner, second))

    assert "topic-complete:strings" not in after_one
    assert "beginner-graduate" not in after_one
    assert "topic-complete:strings" in after_two
    assert "beginner-graduate" in after_two


def test_reaching_level_5_earns_its_badge(learner, topic):
    profile = learner.party.learner_profile
    profile.total_xp = 990
    profile.level = 4
    db.session.commit()

    feedback = solve(learner, make_challenge(topic, "One"))

    assert feedback["level"] == 5
    assert "level-5" in badge_codes(feedback)


def test_ten_unassisted_solves_earn_two_badges(learner, topic):
    challenges = [make_challenge(topic, f"Challenge {n}") for n in range(10)]
    for challenge in challenges[:9]:
        solve(learner, challenge)

    feedback = solve(learner, challenges[9])

    assert "solved-10" in badge_codes(feedback)
    assert "unassisted-10" in badge_codes(feedback)


def test_topic_badge_uses_the_topic_name(topic):
    assert badge_info("topic-complete:strings")["name"] == "Strings Complete"


# ---------------------------------------------------------------------------
# Streaks
# ---------------------------------------------------------------------------

def test_solving_on_consecutive_days_grows_the_streak(learner, topic):
    solve(learner, make_challenge(topic, "One"))
    feedback = solve(learner, make_challenge(topic, "Two"), now=NOW + timedelta(days=1))

    assert feedback["current_streak"] == 2
    assert learner.party.learner_profile.longest_streak == 2


def test_two_solves_on_the_same_day_count_once(learner, topic):
    solve(learner, make_challenge(topic, "One"))
    feedback = solve(learner, make_challenge(topic, "Two"), now=NOW + timedelta(hours=2))

    assert feedback["current_streak"] == 1


def test_a_missed_day_restarts_the_streak_but_keeps_the_longest(learner, topic):
    profile = learner.party.learner_profile
    profile.current_streak = 5
    profile.longest_streak = 5
    profile.last_active_date = date(2026, 9, 25)
    db.session.commit()

    feedback = solve(learner, make_challenge(topic, "One"))

    assert feedback["current_streak"] == 1
    assert profile.longest_streak == 5


def test_streak_days_follow_the_learners_timezone(learner, topic):
    """03:00 UTC on the 28th is still the 27th in Toronto."""
    late_evening_27th = datetime(2026, 9, 28, 3, 0, tzinfo=UTC)
    evening_28th = datetime(2026, 9, 28, 20, 0, tzinfo=UTC)

    solve(learner, make_challenge(topic, "One"), now=late_evening_27th)
    feedback = solve(learner, make_challenge(topic, "Two"), now=evening_28th)

    assert feedback["current_streak"] == 2


def test_displayed_streak_drops_to_zero_after_a_missed_day(learner, topic):
    solve(learner, make_challenge(topic, "One"))
    profile = learner.party.learner_profile
    person = learner.party

    assert displayed_streak(profile, person, NOW + timedelta(days=1)) == 1
    assert displayed_streak(profile, person, NOW + timedelta(days=2)) == 0


def test_a_seven_day_streak_earns_its_badge(learner, topic):
    profile = learner.party.learner_profile
    profile.current_streak = 6
    profile.longest_streak = 6
    profile.last_active_date = date(2026, 9, 27)
    db.session.commit()

    feedback = solve(learner, make_challenge(topic, "One"))

    assert feedback["current_streak"] == 7
    assert "streak-7" in badge_codes(feedback)