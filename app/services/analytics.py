"""
Learner analytics (spec FR14, PR-P1): the numbers behind the dashboard
charts. Built from submissions, which record every attempt with its result
and error type.

Weeks start on Monday 00:00 UTC, matching the weekly leaderboard.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.extensions import db
from app.models import Challenge, ChallengeStatus, Submission, SubmissionStatus, Topic
from app.services.gamification import solved_challenge_ids
from app.services.leaderboard import week_start

WEEKS_SHOWN = 8
TOP_ERRORS = 5


def _as_utc(moment):
    """SQLite returns dates without a timezone, although PyQuest always
    stores UTC; this makes them comparable with timezone-aware dates."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def learner_analytics(account, now=None):
    """Everything the dashboard charts need, as plain data ready for JSON."""
    now = now or datetime.now(UTC)
    rows = db.session.execute(
        select(Submission.status, Submission.error_category, Submission.submitted_at).where(
            Submission.party_id == account.party_id
        )
    ).all()

    # Pass rate by week, for the last WEEKS_SHOWN weeks, oldest first.
    this_week = week_start(now)
    starts = [this_week - timedelta(weeks=n) for n in reversed(range(WEEKS_SHOWN))]
    attempts = dict.fromkeys(starts, 0)
    passes = dict.fromkeys(starts, 0)
    for status, _, submitted_at in rows:
        start = week_start(_as_utc(submitted_at))
        if start in attempts:
            attempts[start] += 1
            if status == SubmissionStatus.PASSED:
                passes[start] += 1

    passed_total = sum(1 for status, _, _ in rows if status == SubmissionStatus.PASSED)
    errors = Counter(error for _, error, _ in rows if error).most_common(TOP_ERRORS)

    return {
        "total_submissions": len(rows),
        "pass_rate": round(100 * passed_total / len(rows)) if rows else None,
        "accuracy": {
            "labels": [start.strftime("%b %d") for start in starts],
            "attempts": [attempts[start] for start in starts],
            # None for weeks with no attempts, so the chart shows a gap
            # rather than a misleading 0%.
            "pass_rate": [
                round(100 * passes[start] / attempts[start]) if attempts[start] else None
                for start in starts
            ],
        },
        "errors": [{"name": name, "count": count} for name, count in errors],
        "topics": _topic_progress(account),
    }


def _topic_progress(account):
    """Solved versus published challenges per topic, in learning-path order."""
    solved = solved_challenge_ids(account.party_id)
    rows = db.session.execute(
        select(Topic.name, Challenge.id)
        .join(Challenge.topic)
        .where(Challenge.status == ChallengeStatus.PUBLISHED)
        .order_by(Topic.sort_order, Topic.name)
    ).all()

    progress = {}
    for topic_name, challenge_id in rows:
        entry = progress.setdefault(topic_name, {"name": topic_name, "solved": 0, "total": 0})
        entry["total"] += 1
        if challenge_id in solved:
            entry["solved"] += 1
    return list(progress.values())