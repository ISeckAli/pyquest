"""
Gamification service: streaks and badges (spec FR08, PR-G1).

Called by grading after every passing submission, inside the same database
transaction, so a solve, its XP, its streak day, and any badges it earns
are saved together or not at all.
"""

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.extensions import db
from app.models import (
    Challenge,
    ChallengeStatus,
    Difficulty,
    LearnerBadge,
    Submission,
    SubmissionStatus,
    Topic,
)


@dataclass(frozen=True)
class BadgeDefinition:
    code: str
    name: str
    description: str
    icon: str


# The badge set (spec FR08, tunable). Per-topic badges are added
# automatically for every topic, with codes like "topic-complete:strings".
BADGES = {
    badge.code: badge
    for badge in [
        BadgeDefinition("first-solve", "First Solve", "Solve your first challenge.", "🎯"),
        BadgeDefinition("solved-10", "Ten Down", "Solve 10 challenges.", "🔟"),
        BadgeDefinition("solved-50", "Half Century", "Solve 50 challenges.", "🏅"),
        BadgeDefinition("level-5", "Level 5", "Reach level 5.", "⭐"),
        BadgeDefinition("level-10", "Level 10", "Reach level 10.", "🌟"),
        BadgeDefinition("streak-7", "Week Streak", "Solve a challenge 7 days in a row.", "🔥"),
        BadgeDefinition("streak-30", "Month Streak", "Solve a challenge 30 days in a row.", "☄️"),
        BadgeDefinition("unassisted-10", "Unassisted", "Solve 10 challenges without AI hints.", "🧠"),
        BadgeDefinition(
            "beginner-graduate", "Beginner Graduate", "Solve every Beginner challenge.", "🎓"
        ),
    ]
}

TOPIC_BADGE_PREFIX = "topic-complete:"


# ---------------------------------------------------------------------------
# Streaks (PR-G1)
# ---------------------------------------------------------------------------

def learner_today(person, now):
    """The date it is for this learner right now, in their own timezone.

    A day counts toward a streak by the learner's calendar, so solving at
    11 p.m. in Toronto counts for that day, not the next day in UTC. An
    unknown timezone falls back to UTC rather than failing.
    """
    try:
        zone = ZoneInfo(person.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = UTC
    return now.astimezone(zone).date()


def record_activity(profile, person, now):
    """Count today toward the learner's streak.

    Solving again on the same day changes nothing. Solving the day after
    the last active day extends the streak; any longer gap restarts it at
    1. The longest streak is always kept.
    """
    today = learner_today(person, now)
    last = profile.last_active_date
    if last == today:
        return

    if last == today - timedelta(days=1):
        profile.current_streak += 1
    else:
        profile.current_streak = 1
    profile.longest_streak = max(profile.longest_streak, profile.current_streak)
    profile.last_active_date = today


def displayed_streak(profile, person, now):
    """The streak to show right now.

    A streak stays alive until the end of the day after the last active
    day. Once a whole day is missed it shows 0, even before the learner's
    next solve resets the stored value, so a broken streak is never shown
    as still running.
    """
    last = profile.last_active_date
    if last is None:
        return 0
    if last >= learner_today(person, now) - timedelta(days=1):
        return profile.current_streak
    return 0


# ---------------------------------------------------------------------------
# Badges (FR08)
# ---------------------------------------------------------------------------

def solved_challenge_ids(party_id):
    """Ids of every challenge the learner has passed at least once."""
    return set(
        db.session.scalars(
            select(Submission.challenge_id)
            .where(
                Submission.party_id == party_id,
                Submission.status == SubmissionStatus.PASSED,
            )
            .distinct()
        )
    )


def unassisted_solve_count(party_id):
    """How many challenges the learner first solved without AI hints."""
    rows = db.session.execute(
        select(Submission.challenge_id, Submission.hints_used)
        .where(
            Submission.party_id == party_id,
            Submission.status == SubmissionStatus.PASSED,
        )
        .order_by(Submission.id)
    ).all()

    first_solve_hints = {}
    for challenge_id, hints_used in rows:
        first_solve_hints.setdefault(challenge_id, hints_used)
    return sum(1 for hints in first_solve_hints.values() if hints == 0)


def _qualifying_codes(party_id, profile):
    """Every badge code the learner currently qualifies for."""
    solved = solved_challenge_ids(party_id)
    codes = set()

    thresholds = [
        (len(solved), 1, "first-solve"),
        (len(solved), 10, "solved-10"),
        (len(solved), 50, "solved-50"),
        (profile.level, 5, "level-5"),
        (profile.level, 10, "level-10"),
        (profile.longest_streak, 7, "streak-7"),
        (profile.longest_streak, 30, "streak-30"),
        (unassisted_solve_count(party_id), 10, "unassisted-10"),
    ]
    codes.update(code for value, needed, code in thresholds if value >= needed)

    published = db.session.execute(
        select(Challenge.id, Challenge.topic_id, Challenge.difficulty).where(
            Challenge.status == ChallengeStatus.PUBLISHED
        )
    ).all()

    by_topic = defaultdict(set)
    beginner_ids = set()
    for challenge_id, topic_id, difficulty in published:
        by_topic[topic_id].add(challenge_id)
        if difficulty == Difficulty.BEGINNER:
            beginner_ids.add(challenge_id)

    if beginner_ids and beginner_ids <= solved:
        codes.add("beginner-graduate")

    topic_slugs = dict(db.session.execute(select(Topic.id, Topic.slug)).all())
    for topic_id, challenge_ids in by_topic.items():
        if challenge_ids <= solved:
            codes.add(f"{TOPIC_BADGE_PREFIX}{topic_slugs[topic_id]}")

    return codes


def award_badges(account, profile):
    """Save any badges the learner has newly qualified for, and return them.

    Does not commit: grading commits the badges together with the passing
    submission that earned them. Badges already earned are never removed,
    even if, say, a new challenge is later added to a completed topic.
    """
    earned = set(
        db.session.scalars(
            select(LearnerBadge.badge_code).where(LearnerBadge.party_id == account.party_id)
        )
    )
    new_codes = sorted(_qualifying_codes(account.party_id, profile) - earned)

    for code in new_codes:
        db.session.add(LearnerBadge(party_id=account.party_id, badge_code=code))
    return [badge_info(code) for code in new_codes]


def badge_info(code):
    """A badge's code, name, description, and icon, ready to display."""
    if code.startswith(TOPIC_BADGE_PREFIX):
        slug = code.removeprefix(TOPIC_BADGE_PREFIX)
        topic = db.session.scalars(select(Topic).where(Topic.slug == slug)).first()
        topic_name = topic.name if topic is not None else slug
        return {
            "code": code,
            "name": f"{topic_name} Complete",
            "description": f"Solve every challenge in {topic_name}.",
            "icon": "📚",
        }
    return asdict(BADGES[code])


def earned_badges(account):
    """The learner's badges, most recent first, each with when it was earned."""
    rows = db.session.scalars(
        select(LearnerBadge)
        .where(LearnerBadge.party_id == account.party_id)
        .order_by(LearnerBadge.earned_at.desc(), LearnerBadge.id.desc())
    ).all()
    return [{**badge_info(row.badge_code), "earned_at": row.earned_at} for row in rows]