"""
Gamification models (spec FR08, FR10, PR-G1).

Badge definitions (names, descriptions, rules) live in code, in
app/services/gamification.py, so they are versioned in Git, reviewed like
any other code, and need no seeding when the app is deployed. The database
stores only which badges each learner has earned, by badge code.

Streak data (current and longest streak, last active day) lives on
LearnerProfile, where the SRS placed it.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
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


class DailyMission(db.Model):
    """One of a learner's missions for one day (spec FR10)."""

    __tablename__ = "daily_mission"

    # A learner gets each kind of mission at most once per day.
    __table_args__ = (UniqueConstraint("party_id", "mission_date", "template"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"))

    # The learner's own calendar date (their timezone). Missions for any
    # other date can no longer be progressed, which is how they expire at
    # the learner's midnight.
    mission_date: Mapped[date] = mapped_column(Date)

    # Which kind of mission, such as "solve-any" (see app/services/missions.py).
    template: Mapped[str] = mapped_column(String(30))

    # What the mission is about, when it needs one: a difficulty such as
    # "intermediate", or a topic slug such as "strings".
    target: Mapped[Optional[str]] = mapped_column(String(60))

    progress: Mapped[int] = mapped_column(default=0)
    goal: Mapped[int] = mapped_column(default=1)
    bonus_xp: Mapped[int] = mapped_column()
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    @property
    def is_completed(self):
        return self.completed_at is not None

    def __repr__(self):
        return f"<DailyMission {self.mission_date} {self.template} {self.progress}/{self.goal}>"