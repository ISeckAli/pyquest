"""
Adaptive recommendations (Part 15): what each learner should try next,
chosen from their own results.

Four rules, checked in order so the most useful suggestion comes first:

1. Struggling: a challenge failed STRUGGLE_FAILURES times without a solve
   leads to an unattempted Beginner challenge in the same topic, to build
   confidence before returning to it.
2. Unfinished: challenges attempted but not solved, most recent first.
3. Step up: once every Beginner challenge in a topic is solved, its first
   unsolved Intermediate challenge.
4. The learning path: the first unsolved challenges in library order
   (topics in order, Beginner before Intermediate).

Rule-based rather than AI, so every suggestion is predictable, explainable,
and free. Solved and unpublished challenges are never suggested.
"""

from dataclasses import dataclass

from sqlalchemy import select

from app.extensions import db
from app.models import Challenge, Difficulty, Submission, SubmissionStatus
from app.services.challenges import list_published

# Failed submissions on one challenge, without a solve, before the learner
# is steered to easier practice first. Tunable.
STRUGGLE_FAILURES = 3
MAX_RECOMMENDATIONS = 3


@dataclass(frozen=True)
class Recommendation:
    challenge: Challenge
    reason: str

    def as_json(self):
        """The recommendation as pages and scripts need it."""
        return {
            "title": self.challenge.title,
            "slug": self.challenge.slug,
            "topic": self.challenge.topic.name,
            "difficulty": self.challenge.difficulty.label,
            "difficulty_value": self.challenge.difficulty.value,
            "reason": self.reason,
        }


def _history(party_id):
    """Solved challenge ids, failure counts, and each challenge's latest attempt."""
    solved = set()
    failures = {}
    latest_attempt = {}
    rows = db.session.execute(
        select(Submission.challenge_id, Submission.status, Submission.submitted_at).where(
            Submission.party_id == party_id
        )
    ).all()
    for challenge_id, status, submitted_at in rows:
        if status == SubmissionStatus.PASSED:
            solved.add(challenge_id)
        else:
            failures[challenge_id] = failures.get(challenge_id, 0) + 1
        previous = latest_attempt.get(challenge_id)
        if previous is None or submitted_at > previous:
            latest_attempt[challenge_id] = submitted_at
    return solved, failures, latest_attempt


def recommendations(account, limit=MAX_RECOMMENDATIONS):
    """Up to `limit` challenges for this learner to try next, best first."""
    published = list_published()
    solved, failures, latest_attempt = _history(account.party_id)
    unsolved = [challenge for challenge in published if challenge.id not in solved]

    picks = []
    chosen = set()

    def add(challenge, reason):
        if challenge is not None and challenge.id not in chosen and len(picks) < limit:
            chosen.add(challenge.id)
            picks.append(Recommendation(challenge, reason))

    started = sorted(
        (challenge for challenge in unsolved if challenge.id in latest_attempt),
        key=lambda challenge: latest_attempt[challenge.id],
        reverse=True,
    )

    # 1. Struggling: practise something easier in the same topic first.
    for challenge in started:
        if failures.get(challenge.id, 0) < STRUGGLE_FAILURES:
            continue
        easier = next(
            (
                other for other in unsolved
                if other.topic_id == challenge.topic_id
                and other.difficulty == Difficulty.BEGINNER
                and other.id not in latest_attempt
            ),
            None,
        )
        if easier is not None:
            add(
                easier,
                f"Practise {challenge.topic.name} with another Beginner challenge, "
                f"then return to {challenge.title}.",
            )
        else:
            add(challenge, "Pick up where you left off. A hint could help you past the tricky part.")

    # 2. Unfinished: attempted but not solved, most recent first.
    for challenge in started:
        add(challenge, "Pick up where you left off.")

    # 3. Step up: every Beginner challenge in a topic solved.
    for topic in dict.fromkeys(challenge.topic for challenge in published):
        in_topic = [challenge for challenge in published if challenge.topic_id == topic.id]
        beginners = [c for c in in_topic if c.difficulty == Difficulty.BEGINNER]
        if beginners and all(c.id in solved for c in beginners):
            harder = next(
                (c for c in in_topic if c.difficulty != Difficulty.BEGINNER and c.id not in solved),
                None,
            )
            add(
                harder,
                f"You've solved every Beginner challenge in {topic.name}. "
                "Ready for an Intermediate one.",
            )

    # 4. The learning path.
    for challenge in unsolved:
        add(challenge, "Next on your learning path.")

    return picks