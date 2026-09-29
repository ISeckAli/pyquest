"""
Guest mode (spec PR-A3): try PyQuest with one click and no sign-up.

A guest is a real learner account marked is_guest, so every feature (grading,
XP, missions, badges, the Coach) works for guests without special cases.
Guests are hidden from the leaderboard, get a small chat allowance, can turn
into a real account and keep all their progress, and are deleted after
GUEST_RETENTION_DAYS by `flask --app app cleanup-guests`.
"""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    AIUsage,
    CoachMessage,
    CoachMessageKind,
    DailyMission,
    Hint,
    LearnerBadge,
    LearnerProfile,
    MessageSender,
    Person,
    RoleType,
    SavedCode,
    Submission,
    UserAccount,
)
from app.services.auth import (
    DISPLAY_NAME_MAX_LENGTH,
    DISPLAY_NAME_MIN_LENGTH,
    RegistrationError,
    normalise_email,
    validate_password,
)

# The .invalid top-level domain is reserved (RFC 2606): addresses on it can
# never receive email, so a guest address can never reach a real inbox.
GUEST_EMAIL_DOMAIN = "guest.pyquest.invalid"

# Tunable (spec PR-A3 and section 5.9).
GUEST_CHAT_LIMIT = 5
GUEST_RETENTION_DAYS = 7


def is_guest(account):
    """True if the signed-in account is a temporary guest account."""
    return account is not None and account.is_authenticated and account.is_guest


def create_guest():
    """Create a temporary guest learner and return their UserAccount."""
    token = secrets.token_hex(8)
    person = Person(
        display_name=f"Guest {token[:4].upper()}",
        email=f"guest-{token}@{GUEST_EMAIL_DOMAIN}",
        is_guest=True,
        leaderboard_visible=False,
    )
    person.add_role(RoleType.LEARNER)

    account = UserAccount(party=person)
    # A long random password that is never shown: no one can log into a
    # guest account, and it cannot be guessed.
    account.set_password(secrets.token_urlsafe(32))

    profile = LearnerProfile(person=person, total_xp=0, level=1, current_streak=0, longest_streak=0)
    db.session.add_all([person, account, profile])
    db.session.commit()
    return account


def convert_guest(account, display_name, email, password):
    """Turn a guest into a real learner account, keeping all their progress.

    Applies the same rules as registration. The account and its id stay the
    same, so every submission, badge, and hint remains attached.

    Raises:
        RegistrationError: if any input breaks the rules or the email is taken.
    """
    person = account.party
    display_name = display_name.strip()
    email = normalise_email(email)

    if not DISPLAY_NAME_MIN_LENGTH <= len(display_name) <= DISPLAY_NAME_MAX_LENGTH:
        raise RegistrationError(
            f"Display name must be {DISPLAY_NAME_MIN_LENGTH} to "
            f"{DISPLAY_NAME_MAX_LENGTH} characters long.",
            "display_name",
        )
    if email.endswith("@" + GUEST_EMAIL_DOMAIN):
        raise RegistrationError("Please use your own email address.", "email")

    validate_password(password, email=email)

    taken = db.session.scalar(
        select(Person.id).where(Person.email == email, Person.id != person.id)
    )
    if taken is not None:
        raise RegistrationError("An account with this email already exists.", "email")

    person.display_name = display_name
    person.email = email
    person.is_guest = False
    person.leaderboard_visible = True
    account.set_password(password)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise RegistrationError("An account with this email already exists.", "email") from None
    return account


def guest_chat_remaining(account):
    """How many Coach chat messages a guest may still send."""
    sent = db.session.scalar(
        select(func.count()).select_from(CoachMessage).where(
            CoachMessage.party_id == account.party_id,
            CoachMessage.kind == CoachMessageKind.CHAT,
            CoachMessage.sender == MessageSender.LEARNER,
        )
    )
    return max(0, GUEST_CHAT_LIMIT - sent)


def delete_expired_guests(now=None):
    """Delete guest accounts older than GUEST_RETENTION_DAYS, with all their data.

    Real accounts are never touched. Returns how many guests were deleted.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=GUEST_RETENTION_DAYS)
    guests = db.session.scalars(
        select(Person).where(Person.is_guest.is_(True), Person.created_at < cutoff)
    ).all()
    if not guests:
        return 0

    ids = [guest.id for guest in guests]
    # Rows that point at a guest go first, in an order that respects the
    # links between them (Coach messages can point at submissions).
    for model in (AIUsage, CoachMessage, Hint, SavedCode, LearnerBadge, DailyMission, Submission):
        db.session.execute(delete(model).where(model.party_id.in_(ids)))

    # Deleting the person also deletes their account, roles, and learner
    # profile, through the cascades on those relationships.
    for guest in guests:
        db.session.delete(guest)
    db.session.commit()
    return len(ids)