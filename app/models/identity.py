"""
Identity models: who takes part in PyQuest and what they are allowed to do.

Implements the Party analysis pattern from the SRS (Part C, Figure 10) and
section 4.1 of the product specification:

    Party (abstract)       shared identity: display name, creation time
      Person               an individual; adds email and preferences
    UserAccount            login credentials belonging to a Party
    Role                   something a Party is allowed to do; one Party
                           can hold several (learner, instructor,
                           system administrator)
    LearnerProfile         learner-only progress data (XP, level, streaks)

Organization, the pattern's other Party subtype, is not used in v1. The
party_type column already records which subtype each row is, so adding it
later means adding one table rather than restructuring existing ones.
"""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utc_now():
    """Return the current time in UTC.

    All timestamps are stored in UTC and converted to a learner's own
    timezone only when displayed, so values from different users and
    servers can be compared directly.
    """
    return datetime.now(UTC)


class RoleType(StrEnum):
    """The roles a Party can hold (SRS: LearnerRole, InstructorRole,
    SystemAdministratorRole).

    The SRS models these as subclasses of Role. They differ in what they
    are allowed to do rather than in the data they store, so in the database
    they are values of a single role_type column. Permission checks use
    these values, and learner-specific data lives in LearnerProfile.
    """

    LEARNER = "learner"
    INSTRUCTOR = "instructor"
    SYSTEM_ADMINISTRATOR = "system_administrator"


class Party(db.Model):
    """Abstract identity shared by every participant.

    Uses joined-table inheritance: common fields live in the party table,
    and each subtype (such as Person) adds its own table joined on the same
    id. party_type records which subtype a row belongs to, so querying
    Party returns Person objects automatically.
    """

    __tablename__ = "party"

    id: Mapped[int] = mapped_column(primary_key=True)
    party_type: Mapped[str] = mapped_column(String(20))
    display_name: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # One login account per party. delete-orphan removes the account when
    # the party is deleted, so no credentials are left behind.
    account: Mapped[Optional["UserAccount"]] = relationship(
        back_populates="party", cascade="all, delete-orphan"
    )

    # Role has two links to party (who holds the role, and who granted it),
    # so foreign_keys states which link this relationship follows.
    roles: Mapped[list["Role"]] = relationship(
        back_populates="party",
        cascade="all, delete-orphan",
        foreign_keys="Role.party_id",
    )

    __mapper_args__ = {"polymorphic_on": "party_type"}

    def has_role(self, role_type):
        """Return True if this party holds the given role."""
        return any(role.role_type == role_type for role in self.roles)

    def add_role(self, role_type, granted_by=None):
        """Grant a role to this party and return the new Role.

        Args:
            role_type: a RoleType value.
            granted_by: the Party granting it (an administrator), or None
                for roles granted automatically, such as learner at sign-up.

        Raises:
            ValueError: if the party already holds this role. The database
                also enforces this with a unique constraint; checking here
                gives a clear message instead of a database error.
        """
        if self.has_role(role_type):
            raise ValueError(f"{self.display_name} already has the {role_type} role.")

        role = Role(
            role_type=role_type,
            granted_by_party_id=granted_by.id if granted_by is not None else None,
        )
        self.roles.append(role)
        return role

    def __repr__(self):
        return f"<{type(self).__name__} {self.id} {self.display_name!r}>"


class Person(Party):
    """An individual taking part in PyQuest (SRS Party subtype Person).

    Collects only what the product needs (spec section 10, data
    minimisation): no phone number, even though the SRS Party class lists
    one.
    """

    __tablename__ = "person"

    id: Mapped[int] = mapped_column(ForeignKey("party.id"), primary_key=True)

    # 254 characters is the longest valid email address. Unique across all
    # people; stored lowercase by the validator below, so the same address
    # typed with different capitals cannot create a second account.
    email: Mapped[str] = mapped_column(String(254), unique=True)

    # An IANA timezone name. Used to decide when a learner's day starts for
    # streaks and daily missions (spec PR-G1, FR10).
    timezone: Mapped[str] = mapped_column(String(64), default="America/Toronto")

    # Learners can hide themselves from the public leaderboard (spec FR09).
    leaderboard_visible: Mapped[bool] = mapped_column(default=True)

    learner_profile: Mapped[Optional["LearnerProfile"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )

    __mapper_args__ = {"polymorphic_identity": "person"}

    @validates("email")
    def _normalise_email(self, key, value):
        """Store email addresses trimmed and lowercase.

        Runs automatically whenever email is set, so no code path can save
        an address in a different form. This is what makes the unique rule
        on email case-insensitive (spec FR01).
        """
        return value.strip().lower()


class UserAccount(db.Model):
    """Login credentials for a Party (SRS Part C UserAccount).

    Kept separate from identity so authentication data can change (password
    resets, lockouts) without touching who the person is.
    """

    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"), unique=True)

    # Only a salted hash is stored, never the password itself (NFR03).
    password_hash: Mapped[str] = mapped_column(String(255))

    # Deactivated accounts cannot log in; their data is kept (spec FR13).
    is_active: Mapped[bool] = mapped_column(default=True)

    # Set when the email address is confirmed (spec PR-A1, release R2).
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Supports login throttling: repeated failures lock the account for a
    # short time (spec FR02).
    failed_login_count: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    party: Mapped["Party"] = relationship(back_populates="account")

    def set_password(self, password):
        """Hash and store a password.

        Werkzeug's default algorithm (scrypt) salts each hash and is
        deliberately slow to compute, which makes guessing passwords from a
        stolen database impractical. It satisfies NFR03's "bcrypt or an
        equivalent strong hashing algorithm". Password rules (minimum length,
        common-password checks) are enforced at registration, not here.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Return True if the password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<UserAccount {self.id} party={self.party_id}>"


class Role(db.Model):
    """A role held by a Party (SRS Part C Role)."""

    __tablename__ = "role"

    # A party can hold each role at most once.
    __table_args__ = (UniqueConstraint("party_id", "role_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"))

    # Stored as the readable value ("learner"), not the Python name
    # ("LEARNER"), so the database reads clearly on its own. native_enum is
    # off so the same column works identically on SQLite and Postgres.
    role_type: Mapped[RoleType] = mapped_column(
        Enum(
            RoleType,
            native_enum=False,
            length=30,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        )
    )

    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Who granted the role, for accountability (spec FR13, PR-M1). Empty for
    # roles granted automatically, such as learner at sign-up.
    granted_by_party_id: Mapped[Optional[int]] = mapped_column(ForeignKey("party.id"))

    party: Mapped["Party"] = relationship(back_populates="roles", foreign_keys=[party_id])

    def __repr__(self):
        return f"<Role {self.role_type} party={self.party_id}>"


class LearnerProfile(db.Model):
    """Learner-only progress data (SRS Learner attributes, spec section 7).

    Separate from Person because only learners earn XP; instructors and
    administrators who do not learn have no profile at all, rather than
    empty XP columns.
    """

    __tablename__ = "learner_profile"

    # The person's id doubles as this table's key: exactly one profile per
    # person, with no separate id to keep in sync.
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)

    total_xp: Mapped[int] = mapped_column(default=0)
    level: Mapped[int] = mapped_column(default=1)
    current_streak: Mapped[int] = mapped_column(default=0)
    longest_streak: Mapped[int] = mapped_column(default=0)
    last_active_date: Mapped[Optional[date]] = mapped_column()

    person: Mapped["Person"] = relationship(back_populates="learner_profile")

    def __repr__(self):
        return f"<LearnerProfile person={self.person_id} xp={self.total_xp} level={self.level}>"