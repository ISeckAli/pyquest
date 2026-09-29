"""
Audit log (spec FR13, PR-M1): a permanent record of administrative
actions: who did what, to whom, and when.

Entries are only ever added, never edited or deleted, so the log can be
trusted as an accountability trail.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.identity import utc_now


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Who acted. Empty for actions taken by the system itself.
    actor_party_id: Mapped[Optional[int]] = mapped_column(ForeignKey("party.id"))

    # A short machine-readable code, such as "role.granted".
    action: Mapped[str] = mapped_column(String(50))

    # Whom the action was about, if anyone.
    target_party_id: Mapped[Optional[int]] = mapped_column(ForeignKey("party.id"))

    # Human-readable detail, such as "instructor".
    details: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

    actor: Mapped[Optional["Party"]] = relationship(foreign_keys=[actor_party_id])  # noqa: F821
    target: Mapped[Optional["Party"]] = relationship(foreign_keys=[target_party_id])  # noqa: F821

    def __repr__(self):
        return f"<AuditLog {self.action} actor={self.actor_party_id} target={self.target_party_id}>"