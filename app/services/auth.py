"""
Authentication service: registration and login rules (spec FR01, FR02).

Views call these functions and translate their errors into form messages.
No function here reads request data or renders pages.

Tunable values (password length, attempt limit, lockout length) come from
the application config, so they are changed in one place (app/config.py).
"""

import math
from datetime import UTC, datetime, timedelta

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount
from app.services.common_passwords import is_common_password

# Shown for both an unknown email and a wrong password, so the message never
# reveals whether an email address is registered (spec FR02).
INVALID_CREDENTIALS_MESSAGE = "Email or password is incorrect."

DISPLAY_NAME_MIN_LENGTH = 2
DISPLAY_NAME_MAX_LENGTH = 50  # Matches the party.display_name column.

# A real hash of a throwaway value, checked when an email is not registered.
# Verifying a password is deliberately slow, so answering "unknown email"
# instantly would let an attacker tell registered emails apart by response
# time. Checking against this hash makes both cases take the same time.
_DUMMY_PASSWORD_HASH = generate_password_hash("pyquest-timing-equaliser")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class AuthError(Exception):
    """Base class for authentication errors. The message is safe to show."""


class RegistrationError(AuthError):
    """Registration input was rejected.

    Attributes:
        field: the form field the message belongs to ("display_name",
            "email", or "password"), so the page can show the message next
            to the right input.
    """

    def __init__(self, message, field):
        super().__init__(message)
        self.field = field


class InvalidCredentialsError(AuthError):
    """The email is not registered or the password is wrong (deliberately
    indistinguishable)."""

    def __init__(self):
        super().__init__(INVALID_CREDENTIALS_MESSAGE)


class AccountLockedError(AuthError):
    """Too many failed attempts; the account is temporarily locked."""

    def __init__(self, minutes):
        unit = "minute" if minutes == 1 else "minutes"
        super().__init__(
            f"Too many failed login attempts. Try again in {minutes} {unit}."
        )


class AccountDeactivatedError(AuthError):
    """The password was correct, but an administrator deactivated the account.

    Raised only after the correct password is given, so it reveals nothing
    to someone who does not know the password.
    """

    def __init__(self):
        super().__init__(
            "This account has been deactivated. Contact an administrator for help."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_utc(moment):
    """Return a datetime as timezone-aware UTC.

    SQLite does not store timezone information, so datetimes read back from
    it have none, while Postgres returns them with a timezone. Python cannot
    compare the two kinds, so every stored time is normalised before use.
    All times are saved in UTC, which makes adding UTC back correct.
    """
    if moment is None:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


def normalise_email(email):
    """Trim and lowercase an email address, matching how Person stores it."""
    return email.strip().lower()


def validate_password(password, email=None):
    """Check a password against the rules in spec FR01.

    Raises:
        RegistrationError: describing the first rule the password breaks.
    """
    min_length = current_app.config["PASSWORD_MIN_LENGTH"]

    if len(password) < min_length:
        raise RegistrationError(
            f"Password must be at least {min_length} characters long.", "password"
        )
    if is_common_password(password):
        raise RegistrationError(
            "That password is too common. Please choose something less predictable.",
            "password",
        )
    # Catches passwords like "aaaaaaaaab" that pass the length rule but are
    # trivial to guess.
    if len(set(password)) < 4:
        raise RegistrationError(
            "Password is too simple. Use a wider mix of characters.", "password"
        )
    if email is not None and password.lower() == normalise_email(email):
        raise RegistrationError(
            "Password must not be the same as your email address.", "password"
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_learner(display_name, email, password):
    """Create a new learner and return their UserAccount.

    Creates the Person, UserAccount, learner Role, and LearnerProfile in a
    single transaction: either all four are saved or none are, so a failure
    part-way can never leave a half-created account.

    Raises:
        RegistrationError: if any input breaks the rules, or the email is
            already registered.
    """
    display_name = display_name.strip()
    email = normalise_email(email)

    if not DISPLAY_NAME_MIN_LENGTH <= len(display_name) <= DISPLAY_NAME_MAX_LENGTH:
        raise RegistrationError(
            f"Display name must be {DISPLAY_NAME_MIN_LENGTH} to "
            f"{DISPLAY_NAME_MAX_LENGTH} characters long.",
            "display_name",
        )

    validate_password(password, email=email)

    if _find_person_by_email(email) is not None:
        raise _email_taken_error()

    person = Person(display_name=display_name, email=email)
    person.add_role(RoleType.LEARNER)

    account = UserAccount(party=person)
    account.set_password(password)

    db.session.add_all([person, account, LearnerProfile(person=person)])

    try:
        db.session.commit()
    except IntegrityError:
        # Two sign-ups with the same email at the same moment can both pass
        # the check above; the database's unique rule catches the second.
        db.session.rollback()
        raise _email_taken_error()

    return account


def _find_person_by_email(email):
    return db.session.scalars(
        select(Person).where(Person.email == normalise_email(email))
    ).first()


def _email_taken_error():
    return RegistrationError("An account with this email already exists.", "email")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def authenticate(email, password, now=None):
    """Check login details and return the UserAccount if they are valid.

    Args:
        email: as typed; capitals and surrounding spaces are ignored.
        password: as typed.
        now: the current time. Defaults to the real time; tests pass a
            fixed value to check lockout timing without waiting.

    Raises:
        InvalidCredentialsError: unknown email or wrong password.
        AccountLockedError: too many recent failures.
        AccountDeactivatedError: correct password, deactivated account.
    """
    now = now or datetime.now(UTC)

    person = _find_person_by_email(email)
    account = person.account if person is not None else None

    if account is None:
        # Spend the same time as a real password check (see
        # _DUMMY_PASSWORD_HASH), then fail with the shared message.
        check_password_hash(_DUMMY_PASSWORD_HASH, password)
        raise InvalidCredentialsError()

    # The lock is checked before the password, so a locked account cannot
    # keep being guessed at. Unknown emails never show this message, which
    # does reveal that a locked email is registered; request rate limiting
    # (spec PR-N3, Part 13) limits how far that can be exploited.
    locked_until = _as_utc(account.locked_until)
    if locked_until is not None and locked_until > now:
        remaining_seconds = (locked_until - now).total_seconds()
        # Round up to whole minutes, so 30 seconds left reads as "1 minute"
        # and exactly 15 minutes left reads as "15 minutes", not 16.
        minutes = max(1, math.ceil(remaining_seconds / 60))
        raise AccountLockedError(minutes)

    if not account.check_password(password):
        _record_failed_attempt(account, now)
        raise InvalidCredentialsError()

    if not account.is_active:
        raise AccountDeactivatedError()

    account.failed_login_count = 0
    account.locked_until = None
    account.last_login_at = now
    db.session.commit()

    return account


def _record_failed_attempt(account, now):
    """Count a failed attempt and lock the account when the limit is reached.

    The counter resets once the account is locked, so after the lock expires
    the user gets the full number of attempts again.
    """
    max_attempts = current_app.config["LOGIN_MAX_FAILED_ATTEMPTS"]
    lockout_minutes = current_app.config["LOGIN_LOCKOUT_MINUTES"]

    account.failed_login_count += 1
    if account.failed_login_count >= max_attempts:
        account.locked_until = now + timedelta(minutes=lockout_minutes)
        account.failed_login_count = 0

    db.session.commit()