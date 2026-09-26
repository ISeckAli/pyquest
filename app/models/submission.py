"""
Submission model: one graded attempt at a challenge (spec section 7, FR06).

Every Submit is recorded, passed or failed. Besides deciding XP, these
records are the data behind progress analytics (spec PR-P1): accuracy over
time, common error types, time spent, and hint use.

The SRS Submission state diagram (Part C, Figure 6) runs Created ->
Executing -> Evaluating -> Passed or Failed. Under decision DR-03 the first
three states happen in the learner's browser; the server records the
outcome, so only the two final states are stored.
"""

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.challenge import _enum_type
from app.models.identity import utc_now


class SubmissionStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class Submission(db.Model):
    __tablename__ = "submission"

    # Speeds up the most common question asked of this table: "has this
    # person already solved this challenge?" (checked on every submit).
    __table_args__ = (
        Index("ix_submission_party_id_challenge_id", "party_id", "challenge_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"))
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenge.id"))

    # The code exactly as submitted, kept so learners can review past
    # attempts and the AI Coach can explain a failure (spec PR-C2).
    code: Mapped[str] = mapped_column(Text)

    status: Mapped[SubmissionStatus] = mapped_column(_enum_type(SubmissionStatus))
    passed_count: Mapped[int] = mapped_column()
    total_count: Mapped[int] = mapped_column()

    # The Python error type, such as "NameError", if the code raised one.
    # Grouped in analytics as the learner's most common mistakes.
    error_category: Mapped[Optional[str]] = mapped_column(String(40))

    # How long the code took to run in the browser, as reported by it.
    execution_ms: Mapped[Optional[int]] = mapped_column()

    # AI hints used before this submission; reduces XP (spec PR-L3, Part 7).
    hints_used: Mapped[int] = mapped_column(default=0)

    # XP earned by this submission: the challenge's value on the first
    # passing submission, otherwise 0.
    xp_awarded: Mapped[int] = mapped_column(default=0)

    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    party: Mapped["Party"] = relationship()  # noqa: F821
    challenge: Mapped["Challenge"] = relationship()  # noqa: F821

    @property
    def passed(self):
        return self.status == SubmissionStatus.PASSED

    def __repr__(self):
        return f"<Submission {self.id} {self.status} challenge={self.challenge_id}>"