"""
SavedCode model: a learner's latest editor contents for one challenge
(spec FR05, section 7).

Kept separate from Submission: submissions are graded snapshots that are
never changed, while saved code is a single working copy per learner per
challenge that is overwritten as they type, so leaving the page and coming
back never loses work.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.identity import utc_now


class SavedCode(db.Model):
    __tablename__ = "saved_code"

    # Exactly one working copy per learner per challenge.
    __table_args__ = (UniqueConstraint("party_id", "challenge_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"))
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenge.id"))
    code: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    def __repr__(self):
        return f"<SavedCode party={self.party_id} challenge={self.challenge_id}>"