"""
Daily missions (spec FR10).

Each learner gets three missions per day, created the first time they
visit or solve that day, by their own calendar. Completing one awards bonus
XP. Missions progress only on first solves, so repeating an already-solved
challenge cannot farm mission XP day after day.
"""

import random
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import select

from app.extensions import db
from app.models import Challenge, ChallengeStatus, DailyMission, Difficulty, Topic
from app.services.gamification import learner_today, solved_challenge_ids

MISSIONS_PER_DAY = 3
MISSION_BONUS_XP = 15  # Spec FR10 (tunable).

SOLVE_ANY = "solve-any"
SOLVE_DIFFICULTY = "solve-difficulty"
SOLVE_UNASSISTED = "solve-unassisted"
SOLVE_TWO_IN_TOPIC = "solve-two-in-topic"


def _missions_on(party_id, day):
    return db.session.scalars(
        select(DailyMission)
        .where(DailyMission.party_id == party_id, DailyMission.mission_date == day)
        .order_by(DailyMission.id)
    ).all()


def todays_missions(account, now=None, commit=True):
    """The learner's missions for today, created if this is their first visit.

    Args:
        commit: False when called inside another transaction (grading), so
            the new missions are saved together with that transaction.
    """
    now = now or datetime.now(UTC)
    day = learner_today(account.party, now)
    missions = _missions_on(account.party_id, day)
    if not missions:
        missions = _create_missions(account, day)
        if commit:
            db.session.commit()
    return missions


def _create_missions(account, day):
    """Choose today's missions and add them to the session.

    Always includes "solve any challenge". The others are chosen from
    missions the learner can actually complete: a difficulty or topic is
    only offered if unsolved challenges fit it. The choice is random but
    seeded by learner and date, so it stays the same all day and tests can
    rely on it.
    """
    rng = random.Random(f"{account.party_id}:{day.isoformat()}")
    solved = solved_challenge_ids(account.party_id)

    unsolved = [
        (difficulty, topic_slug)
        for challenge_id, difficulty, topic_slug in db.session.execute(
            select(Challenge.id, Challenge.difficulty, Topic.slug)
            .join(Challenge.topic)
            .where(Challenge.status == ChallengeStatus.PUBLISHED)
        ).all()
        if challenge_id not in solved
    ]

    options = [(SOLVE_UNASSISTED, None, 1)]

    difficulties = sorted({difficulty for difficulty, _ in unsolved}, key=lambda d: d.rank)
    if difficulties:
        options.append((SOLVE_DIFFICULTY, rng.choice(difficulties).value, 1))

    topic_counts = Counter(topic_slug for _, topic_slug in unsolved)
    topics = sorted(slug for slug, count in topic_counts.items() if count >= 2)
    if topics:
        options.append((SOLVE_TWO_IN_TOPIC, rng.choice(topics), 2))

    chosen = [(SOLVE_ANY, None, 1)] + rng.sample(options, min(len(options), MISSIONS_PER_DAY - 1))

    missions = [
        DailyMission(
            party_id=account.party_id,
            mission_date=day,
            template=template,
            target=target,
            goal=goal,
            progress=0,
            bonus_xp=MISSION_BONUS_XP,
        )
        for template, target, goal in chosen
    ]
    db.session.add_all(missions)
    db.session.flush()
    return missions


def _counts_toward(mission, challenge, submission):
    if mission.template == SOLVE_ANY:
        return True
    if mission.template == SOLVE_DIFFICULTY:
        return challenge.difficulty.value == mission.target
    if mission.template == SOLVE_UNASSISTED:
        return submission.hints_used == 0
    if mission.template == SOLVE_TWO_IN_TOPIC:
        return challenge.topic.slug == mission.target
    return False


def progress_missions(account, challenge, submission, now):
    """Advance today's missions for a first solve and return any it completed.

    Does not commit: grading saves mission progress and bonus XP together
    with the solve that earned them.
    """
    completed = []
    for mission in todays_missions(account, now, commit=False):
        if mission.is_completed or not _counts_toward(mission, challenge, submission):
            continue
        mission.progress += 1
        if mission.progress >= mission.goal:
            mission.completed_at = now
            completed.append(mission)
    return completed


def _with_article(word):
    """ "an Intermediate", "an Advanced", "a Beginner": the article that
    fits the word's first letter."""
    return f"{'an' if word[:1].lower() in 'aeiou' else 'a'} {word}"


def describe(mission):
    """A mission ready to display."""
    if mission.template == SOLVE_ANY:
        title = "Solve any challenge"
    elif mission.template == SOLVE_DIFFICULTY:
        title = f"Solve {_with_article(Difficulty(mission.target).label)} challenge"
    elif mission.template == SOLVE_UNASSISTED:
        title = "Solve a challenge without AI hints"
    else:
        topic = db.session.scalars(select(Topic).where(Topic.slug == mission.target)).first()
        topic_name = topic.name if topic is not None else mission.target
        title = f"Solve {mission.goal} challenges in {topic_name}"

    return {
        "id": mission.id,
        "template": mission.template,
        "title": title,
        "progress": mission.progress,
        "goal": mission.goal,
        "completed": mission.is_completed,
        "bonus_xp": mission.bonus_xp,
    }