"""
Coach progress summaries (spec PR-C5): a short note on the learner's
strengths and what to practise next, at most one per day.

Built only from the learner's statistics. The Coach never sees their name,
email, or code for this, since a summary needs none of them. Uses the same
standing rules, daily AI limit, and fallback approach as the other Coach
features, sharing helpers internal to the Coach (see coach_chat.py).
"""

from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select

from app.extensions import db
from app.models import CoachMessage, CoachMessageKind, ContentSource, MessageSender
from app.services.ai_service import AIUnavailableError, generate
from app.services.analytics import learner_analytics
from app.services.coach import (
    DAILY_AI_CALL_LIMIT,
    MAX_REPLY_LENGTH,
    SYSTEM_RULES,
    CoachError,
    _ai_calls_today,
    _record_ai_call,
    _today,
)


def todays_summary(account, now=None):
    """The learner's summary from today (UTC), or None."""
    now = now or datetime.now(UTC)
    start = datetime.combine(_today(now), time.min, tzinfo=UTC)
    return db.session.scalars(
        select(CoachMessage)
        .where(
            CoachMessage.party_id == account.party_id,
            CoachMessage.kind == CoachMessageKind.SUMMARY,
            CoachMessage.created_at >= start,
            CoachMessage.created_at < start + timedelta(days=1),
        )
        .order_by(CoachMessage.id.desc())
    ).first()


def create_summary(account, now=None):
    """Write today's summary, or return it if one already exists.

    Raises:
        CoachError: if the learner has not submitted anything yet.
    """
    now = now or datetime.now(UTC)
    existing = todays_summary(account, now)
    if existing is not None:
        return existing

    stats = learner_analytics(account, now)
    if not stats["total_submissions"]:
        raise CoachError("Submit a few solutions first, then the Coach can summarise your progress.")

    reply = _ask_ai(account, _prompt(stats), _today(now))
    summary = CoachMessage(
        party_id=account.party_id,
        kind=CoachMessageKind.SUMMARY,
        sender=MessageSender.COACH,
        content=reply if reply is not None else _fallback(stats),
        source=ContentSource.AI if reply is not None else ContentSource.FALLBACK,
        created_at=now,
    )
    db.session.add(summary)
    db.session.commit()
    return summary


def _ask_ai(account, prompt, day):
    """The AI's summary, or None to use the built-in one."""
    if _ai_calls_today(account.party_id, day) >= DAILY_AI_CALL_LIMIT:
        return None
    try:
        reply = generate(SYSTEM_RULES, prompt)
    except AIUnavailableError:
        return None
    _record_ai_call(account.party_id, "summary", day)
    reply = reply.strip()[:MAX_REPLY_LENGTH]
    # A summary never needs code, so a reply containing a code block is
    # treated as unusable.
    return None if "```" in reply else reply


def _prompt(stats):
    topics = "; ".join(f"{t['name']}: {t['solved']} of {t['total']} solved" for t in stats["topics"])
    errors = ", ".join(f"{e['name']} ({e['count']})" for e in stats["errors"]) or "none"
    return (
        "Summarise this learner's progress in PyQuest, speaking to them directly. "
        "Their statistics:\n"
        f"- Submissions: {stats['total_submissions']}, pass rate {stats['pass_rate']}%\n"
        f"- Submissions this week: {stats['accuracy']['attempts'][-1]}\n"
        f"- Most common errors: {errors}\n"
        f"- Topics: {topics or 'none yet'}\n\n"
        "Write at most four short sentences: one genuine strength, one specific area "
        "to practise with a concrete suggestion, and one encouraging next step. Refer "
        "only to these statistics. Do not write code."
    )


def _fallback(stats):
    """A built-in summary from the same statistics, used when the AI is not."""
    parts = [
        f"You have made {stats['total_submissions']} submissions with a "
        f"{stats['pass_rate']}% pass rate."
    ]

    started = [t for t in stats["topics"] if t["solved"] > 0]
    if started:
        best = max(started, key=lambda t: t["solved"] / t["total"])
        parts.append(f"Your strongest topic is {best['name']} ({best['solved']} of {best['total']} solved).")

    if stats["errors"]:
        parts.append(
            f"Your most common error is {stats['errors'][0]['name']}: reading the full "
            "message and the line it names is the quickest way to fix it."
        )

    unfinished = [t for t in stats["topics"] if t["solved"] < t["total"]]
    if unfinished:
        next_topic = min(unfinished, key=lambda t: t["solved"] / t["total"])
        parts.append(f"Next, try a challenge in {next_topic['name']}.")
    return " ".join(parts)