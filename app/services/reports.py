"""
Engagement reports and CSV export for administrators (spec FR15).

Guests are left out of learner counts and the export: they are temporary
and would skew engagement figures. They are counted separately, since how
many visitors try the site is useful on its own.
"""

import csv
import io
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    ContentSource,
    Hint,
    LearnerProfile,
    Person,
    Submission,
    SubmissionStatus,
)

PERIODS = (7, 30, 90)
DEFAULT_PERIOD = 30

# Spreadsheet programs run a cell as a formula when it starts with one of
# these characters. User-typed text (such as a display name) starting with
# one could run a formula on the admin's computer when the file is opened
# ("CSV injection"), so such cells are prefixed with an apostrophe, which
# spreadsheets display as plain text.
FORMULA_STARTERS = ("=", "+", "-", "@", "\t", "\r")

CSV_HEADER = [
    "Name", "Email", "Joined", "Level", "Total XP",
    "Challenges solved", "Submissions", "Last active",
]


def _registered_learners():
    """A query over registered (non-guest) people who have a learner profile."""
    return (
        select(Person)
        .join(LearnerProfile, LearnerProfile.person_id == Person.id)
        .where(Person.is_guest.is_(False))
    )


def _count(statement):
    return db.session.scalar(select(func.count()).select_from(statement.subquery()))


def engagement_summary(days=DEFAULT_PERIOD, now=None):
    """Headline figures for the last `days` days."""
    now = now or datetime.now(UTC)
    start = now - timedelta(days=days)

    submissions = db.session.execute(
        select(Submission.party_id, Submission.status)
        .join(Person, Person.id == Submission.party_id)
        .where(Submission.submitted_at >= start, Person.is_guest.is_(False))
    ).all()
    passed = sum(1 for _, status in submissions if status == SubmissionStatus.PASSED)

    return {
        "days": days,
        "learners": _count(_registered_learners()),
        "new_learners": _count(_registered_learners().where(Person.created_at >= start)),
        "active_learners": len({party_id for party_id, _ in submissions}),
        "guests": _count(
            select(Person).where(Person.is_guest.is_(True), Person.created_at >= start)
        ),
        "submissions": len(submissions),
        "solves": passed,
        "pass_rate": round(100 * passed / len(submissions)) if submissions else None,
        "ai_hints": _count(
            select(Hint).where(Hint.source == ContentSource.AI, Hint.created_at >= start)
        ),
    }


def learner_rows():
    """One row per registered learner, highest XP first."""
    people = db.session.execute(
        select(
            Person.id, Person.display_name, Person.email, Person.created_at,
            LearnerProfile.level, LearnerProfile.total_xp, LearnerProfile.last_active_date,
        )
        .join(LearnerProfile, LearnerProfile.person_id == Person.id)
        .where(Person.is_guest.is_(False))
        .order_by(LearnerProfile.total_xp.desc(), Person.display_name)
    ).all()

    submission_counts = dict(
        db.session.execute(
            select(Submission.party_id, func.count()).group_by(Submission.party_id)
        ).all()
    )
    solved_counts = dict(
        db.session.execute(
            select(Submission.party_id, func.count(func.distinct(Submission.challenge_id)))
            .where(Submission.status == SubmissionStatus.PASSED)
            .group_by(Submission.party_id)
        ).all()
    )

    return [
        [
            name,
            email,
            created_at.strftime("%Y-%m-%d"),
            level,
            total_xp,
            solved_counts.get(person_id, 0),
            submission_counts.get(person_id, 0),
            last_active.isoformat() if last_active else "",
        ]
        for person_id, name, email, created_at, level, total_xp, last_active in people
    ]


def _safe_cell(value):
    """A value safe to put in a spreadsheet cell (see FORMULA_STARTERS)."""
    text = str(value)
    return "'" + text if text.startswith(FORMULA_STARTERS) else text


def learners_csv():
    """The learner rows as CSV text, with a header row."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADER)
    for row in learner_rows():
        writer.writerow([_safe_cell(value) for value in row])
    return output.getvalue()