"""
AI Coach models (spec section 5.9, section 7).

    Hint           a hint given for a challenge: level 1 to 3, from the AI
                   or from the instructor's fallback hints (PR-C1)
    CoachMessage   a Coach reply or a learner's chat message: failure
                   explanations (PR-C2), chat (PR-C4), code reviews (PR-C3),
                   and later progress summaries (PR-C5)
    AIUsage        how many AI calls a learner made per day, so the free AI
                   quota is shared fairly (spec section 5.9, limits)
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.challenge import _enum_type
from app.models.identity import utc_now


class ContentSource(StrEnum):
    """Where a piece of Coach content came from.

    Stored as plain text (see _enum_type), so adding a value here needs no
    database migration.
    """

    AI = "ai"
    FALLBACK = "fallback"  # Instructor-written, or a general message.
    LEARNER = "learner"  # A learner's own chat message.


class CoachMessageKind(StrEnum):
    EXPLANATION = "explanation"  # "Why did this fail?" (PR-C2)
    CHAT = "chat"  # Ask the Coach (PR-C4)
    REVIEW = "review"  # Code review after passing (PR-C3)
    SUMMARY = "summary"  # Progress coaching (PR-C5, Part 10)


class MessageSender(StrEnum):
    LEARNER = "learner"
    COACH = "coach"


class Hint(db.Model):
    """One hint given to a learner for a challenge (PR-C1)."""

    __tablename__ = "hint"

    # Counting a learner's hints for a challenge happens on every hint
    # request and every passing submission (the XP cost), so it is indexed.
    __table_args__ = (Index("ix_hint_party_id_challenge_id", "party_id", "challenge_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"))
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenge.id"))

    # 1 is a gentle nudge, 3 points at the exact step (spec PR-C1).
    level: Mapped[int] = mapped_column()

    text: Mapped[str] = mapped_column(Text)
    source: Mapped[ContentSource] = mapped_column(_enum_type(ContentSource))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    def __repr__(self):
        return f"<Hint level={self.level} {self.source} challenge={self.challenge_id}>"


class CoachMessage(db.Model):
    """A Coach reply, or in chat a learner's message (spec section 7)."""

    __tablename__ = "coach_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"))

    # Empty for messages not tied to one challenge, such as progress summaries.
    challenge_id: Mapped[Optional[int]] = mapped_column(ForeignKey("challenge.id"))

    # The submission an explanation is about, so each failed submission gets
    # at most one explanation.
    submission_id: Mapped[Optional[int]] = mapped_column(ForeignKey("submission.id"))

    kind: Mapped[CoachMessageKind] = mapped_column(_enum_type(CoachMessageKind))
    sender: Mapped[MessageSender] = mapped_column(_enum_type(MessageSender))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[ContentSource] = mapped_column(_enum_type(ContentSource))

    # The learner's thumbs up or down on a Coach reply (spec PR-C6).
    rating: Mapped[Optional[str]] = mapped_column(String(10))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    def __repr__(self):
        return f"<CoachMessage {self.kind} {self.sender} {self.source}>"


class AIUsage(db.Model):
    """AI calls made for one learner, one day, one Coach feature."""

    __tablename__ = "ai_usage"
    __table_args__ = (UniqueConstraint("party_id", "usage_date", "feature"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"))
    usage_date: Mapped[date] = mapped_column(Date)
    feature: Mapped[str] = mapped_column(String(20))
    count: Mapped[int] = mapped_column(default=0)

    def __repr__(self):
        return f"<AIUsage {self.usage_date} {self.feature}={self.count}>"