"""
Instructor analytics (spec FR15): how each challenge is going for learners,
so instructors can spot challenges that are unclear, too hard, or have a
wrong test.
"""

from collections import Counter, defaultdict

from sqlalchemy import func, select

from app.extensions import db
from app.models import ContentSource, Hint, Submission, SubmissionStatus
from app.services.challenges import list_manageable

# A challenge "needs attention" when at least this many learners have tried
# it and fewer than LOW_SOLVE_RATE percent of them solved it (tunable). The
# minimum stops a single unlucky learner from flagging a challenge.
MIN_LEARNERS_FOR_FLAG = 3
LOW_SOLVE_RATE = 40


def _percent(part, whole):
    return round(100 * part / whole) if whole else None


def challenge_stats(account):
    """One row of statistics per challenge the account may manage.

    Instructors see their own challenges and administrators see all, the
    same rule as the instructor challenge list.
    """
    challenges = list_manageable(account)
    if not challenges:
        return []
    ids = [challenge.id for challenge in challenges]

    tallies = defaultdict(
        lambda: {"attempts": 0, "passed": 0, "learners": set(), "solvers": set(), "errors": Counter()}
    )
    for challenge_id, party_id, status, error in db.session.execute(
        select(
            Submission.challenge_id,
            Submission.party_id,
            Submission.status,
            Submission.error_category,
        ).where(Submission.challenge_id.in_(ids))
    ).all():
        tally = tallies[challenge_id]
        tally["attempts"] += 1
        tally["learners"].add(party_id)
        if status == SubmissionStatus.PASSED:
            tally["passed"] += 1
            tally["solvers"].add(party_id)
        if error:
            tally["errors"][error] += 1

    ai_hints = dict(
        db.session.execute(
            select(Hint.challenge_id, func.count())
            .where(Hint.challenge_id.in_(ids), Hint.source == ContentSource.AI)
            .group_by(Hint.challenge_id)
        ).all()
    )

    rows = []
    for challenge in challenges:
        tally = tallies[challenge.id]
        learners = len(tally["learners"])
        solvers = len(tally["solvers"])
        solve_rate = _percent(solvers, learners)
        top_error = tally["errors"].most_common(1)
        rows.append({
            "id": challenge.id,
            "title": challenge.title,
            "status": challenge.status.value,
            "attempts": tally["attempts"],
            "learners": learners,
            "solvers": solvers,
            "solve_rate": solve_rate,
            "pass_rate": _percent(tally["passed"], tally["attempts"]),
            "top_error": top_error[0][0] if top_error else None,
            "ai_hints": ai_hints.get(challenge.id, 0),
            "needs_attention": learners >= MIN_LEARNERS_FOR_FLAG and solve_rate < LOW_SOLVE_RATE,
        })
    return rows