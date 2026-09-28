"""
Leaderboard service (spec FR09).

Two boards: all-time total XP, and XP earned this week (including daily
mission bonuses). Only display name, level, and XP are ever shown. Learners
who opted out in Settings, deactivated accounts, and learners with no XP
yet are left out.

The week starts on Monday at 00:00 UTC. Streaks and missions follow each
learner's own timezone, but a shared board needs one shared cut-off, so
everyone's week starts at the same moment.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select

from app.extensions import db
from app.models import DailyMission, LearnerProfile, Person, Submission, UserAccount

ALL_TIME = "all"
THIS_WEEK = "week"
PERIODS = (ALL_TIME, THIS_WEEK)
TOP_COUNT = 50  # Spec FR09 (tunable).


@dataclass(frozen=True)
class Standing:
    rank: int
    party_id: int
    display_name: str
    level: int
    xp: int


def week_start(now):
    """Monday 00:00 UTC of the week containing now."""
    today = now.astimezone(UTC).date()
    monday = today - timedelta(days=today.weekday())
    return datetime.combine(monday, time.min, tzinfo=UTC)


def _eligible_learners():
    """(party id, display name, level, total XP) for everyone who may appear."""
    return db.session.execute(
        select(Person.id, Person.display_name, LearnerProfile.level, LearnerProfile.total_xp)
        .join(LearnerProfile, LearnerProfile.person_id == Person.id)
        .join(UserAccount, UserAccount.party_id == Person.id)
        .where(Person.leaderboard_visible.is_(True), UserAccount.is_active.is_(True))
    ).all()


def _weekly_xp(start):
    """XP earned since start, per learner: first solves plus mission bonuses."""
    totals = {}
    for party_id, xp in db.session.execute(
        select(Submission.party_id, func.sum(Submission.xp_awarded))
        .where(Submission.submitted_at >= start)
        .group_by(Submission.party_id)
    ).all():
        totals[party_id] = totals.get(party_id, 0) + (xp or 0)

    for party_id, xp in db.session.execute(
        select(DailyMission.party_id, func.sum(DailyMission.bonus_xp))
        .where(DailyMission.completed_at >= start)
        .group_by(DailyMission.party_id)
    ).all():
        totals[party_id] = totals.get(party_id, 0) + (xp or 0)

    return totals


def standings(period=ALL_TIME, now=None):
    """Every eligible learner with XP, ranked.

    Ties share a rank, as in sports standings: 1, 2, 2, 4. Equal XP is then
    listed alphabetically so the order is stable.
    """
    now = now or datetime.now(UTC)
    learners = _eligible_learners()

    if period == THIS_WEEK:
        weekly = _weekly_xp(week_start(now))
        scored = [(pid, name, level, weekly.get(pid, 0)) for pid, name, level, _ in learners]
    else:
        scored = list(learners)

    scored = [row for row in scored if row[3] > 0]
    scored.sort(key=lambda row: (-row[3], row[1].lower(), row[0]))

    result = []
    for position, (party_id, name, level, xp) in enumerate(scored, start=1):
        rank = result[-1].rank if result and result[-1].xp == xp else position
        result.append(Standing(rank, party_id, name, level, xp))
    return result


def leaderboard(period=ALL_TIME, viewer=None, limit=TOP_COUNT, now=None):
    """The top of the board, plus the viewer's own standing if they are below it.

    Returns:
        (top, viewer_standing): viewer_standing is None when the viewer is
        already in the top list, is not ranked, or no viewer was given.
    """
    everyone = standings(period, now)
    top = everyone[:limit]

    viewer_standing = None
    if viewer is not None:
        top_ids = {standing.party_id for standing in top}
        if viewer.party_id not in top_ids:
            viewer_standing = next(
                (s for s in everyone if s.party_id == viewer.party_id), None
            )
    return top, viewer_standing