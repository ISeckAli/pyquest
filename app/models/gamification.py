"""
Gamification models (spec FR08, PR-G1).

Badge definitions (names, descriptions, rules) live in code, in
app/services/gamification.py, so they are versioned in Git, reviewed like
any other code, and need no seeding when the app is deployed. The database
stores only which badges each learner has earned, by badge code.

Streak data (current and longest streak, last active day) lives on
LearnerProfile, where the SRS placed it.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.identity import utc_now


class LearnerBadge(db.Model):
    """A badge a learner has earned."""

    __tablename__ = "learner_badge"

    # Each badge can be earned only once (spec FR08).
    __table_args__ = (UniqueConstraint("party_id", "badge_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"))

    # A code from the badge definitions, such as "first-solve", or
    # "topic-complete:strings" for per-topic badges.
    badge_code: Mapped[str] = mapped_column(String(80))

    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    def __repr__(self):
        return f"<LearnerBadge {self.badge_code} party={self.party_id}>"