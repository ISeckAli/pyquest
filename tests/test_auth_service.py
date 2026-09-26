"""
Tests for the authentication service (spec FR01, FR02, NFR03).

Registration tests check that every rule in FR01 is enforced and that a
rejected registration saves nothing. Login tests use a fixed `now` so that
lockout timing can be checked instantly, without waiting 15 real minutes.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import LearnerProfile, Person, Role, RoleType, UserAccount
from app.services.auth import (
    INVALID_CREDENTIALS_MESSAGE,
    AccountDeactivatedError,
    AccountLockedError,
    InvalidCredentialsError,
    RegistrationError,
    authenticate,
    register_learner,
)

# A password that passes every rule: long enough, not common, varied.
GOOD_PASSWORD = "violet-harbour-42"

# A fixed moment used by the lockout tests.
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


def count_rows(model):
    """Return how many rows a model's table holds in the database."""
    return db.session.scalar(select(func.count()).select_from(model))


def register(display_name="Ada", email="ada@example.com", password=GOOD_PASSWORD):
    """Register a learner with valid defaults, overriding only what a test needs."""
    return register_learner(display_name, email, password)


def fail_login(times, now=NOW):
    """Make a number of failed login attempts with a wrong password."""
    for _ in range(times):
        with pytest.raises(InvalidCredentialsError):
            authenticate("ada@example.com", "wrong-password-123", now=now)


# ---------------------------------------------------------------------------
# Registration (FR01)
# ---------------------------------------------------------------------------

def test_registration_creates_all_four_records(app):
    """One sign-up creates the Person, account, learner role, and profile."""
    register()
    db.session.expire_all()

    person = db.session.scalars(select(Person)).one()

    assert count_rows(Person) == 1
    assert count_rows(UserAccount) == 1
    assert count_rows(Role) == 1
    assert count_rows(LearnerProfile) == 1
    assert person.has_role(RoleType.LEARNER)
    assert person.learner_profile.total_xp == 0


def test_registration_normalises_email_and_display_name(app):
    register(display_name="  Ada  ", email="  Ada@Example.COM ")
    db.session.expire_all()

    person = db.session.scalars(select(Person)).one()

    assert person.email == "ada@example.com"
    assert person.display_name == "Ada"


def test_registration_rejects_existing_email_in_any_capitals(app):
    register(email="ada@example.com")

    with pytest.raises(RegistrationError) as error:
        register(display_name="Other Ada", email="ADA@example.com")

    assert error.value.field == "email"
    assert count_rows(Person) == 1


def test_registration_rejects_short_password(app):
    with pytest.raises(RegistrationError) as error:
        register(password="short-pw")

    assert error.value.field == "password"
    assert count_rows(Person) == 0


def test_registration_rejects_common_password_in_any_capitals(app):
    with pytest.raises(RegistrationError) as error:
        register(password="Password123")

    assert error.value.field == "password"
    assert count_rows(Person) == 0


def test_registration_rejects_password_with_too_few_different_characters(app):
    with pytest.raises(RegistrationError) as error:
        register(password="aaaaabbbbb")

    assert error.value.field == "password"


def test_registration_rejects_password_matching_email(app):
    with pytest.raises(RegistrationError) as error:
        register(email="ada@example.com", password="ADA@example.com")

    assert error.value.field == "password"


@pytest.mark.parametrize("display_name", ["A", "   ", "x" * 51])
def test_registration_rejects_display_name_outside_length_limits(app, display_name):
    """Too short, blank (only spaces), and too long are all refused."""
    with pytest.raises(RegistrationError) as error:
        register(display_name=display_name)

    assert error.value.field == "display_name"
    assert count_rows(Person) == 0


def test_registration_never_stores_the_plain_password(app):
    register()
    db.session.expire_all()

    account = db.session.scalars(select(UserAccount)).one()

    assert GOOD_PASSWORD not in account.password_hash


# ---------------------------------------------------------------------------
# Login (FR02)
# ---------------------------------------------------------------------------

def test_login_succeeds_with_correct_details(app):
    registered = register()

    account = authenticate("ada@example.com", GOOD_PASSWORD, now=NOW)

    assert account.id == registered.id
    assert account.last_login_at is not None


def test_login_ignores_email_capitals_and_spaces(app):
    register()

    account = authenticate("  ADA@example.com ", GOOD_PASSWORD, now=NOW)

    assert account is not None


def test_wrong_password_and_unknown_email_give_identical_errors(app):
    """FR02: the message must not reveal whether an email is registered."""
    register()

    with pytest.raises(InvalidCredentialsError) as wrong_password:
        authenticate("ada@example.com", "wrong-password-123", now=NOW)
    with pytest.raises(InvalidCredentialsError) as unknown_email:
        authenticate("nobody@example.com", "wrong-password-123", now=NOW)

    assert str(wrong_password.value) == str(unknown_email.value)
    assert str(wrong_password.value) == INVALID_CREDENTIALS_MESSAGE


def test_account_locks_after_too_many_failed_attempts(app):
    """FR02: five failures lock the account, even against the right password."""
    register()
    fail_login(5)

    with pytest.raises(AccountLockedError):
        authenticate("ada@example.com", GOOD_PASSWORD, now=NOW + timedelta(minutes=1))


def test_lock_message_reports_whole_minutes_remaining(app):
    register()
    fail_login(5)

    with pytest.raises(AccountLockedError) as at_lock_time:
        authenticate("ada@example.com", GOOD_PASSWORD, now=NOW)
    with pytest.raises(AccountLockedError) as near_the_end:
        authenticate(
            "ada@example.com", GOOD_PASSWORD, now=NOW + timedelta(minutes=14, seconds=30)
        )

    assert "15 minutes" in str(at_lock_time.value)
    assert "1 minute." in str(near_the_end.value)


def test_lock_expires_after_lockout_period(app):
    register()
    fail_login(5)

    account = authenticate("ada@example.com", GOOD_PASSWORD, now=NOW + timedelta(minutes=16))

    assert account.failed_login_count == 0
    assert account.locked_until is None


def test_successful_login_resets_failed_attempt_count(app):
    register()
    fail_login(2)

    account = authenticate("ada@example.com", GOOD_PASSWORD, now=NOW)

    assert account.failed_login_count == 0


def test_deactivated_account_is_only_revealed_to_the_correct_password(app):
    account = register()
    account.is_active = False
    db.session.commit()

    with pytest.raises(InvalidCredentialsError):
        authenticate("ada@example.com", "wrong-password-123", now=NOW)
    with pytest.raises(AccountDeactivatedError):
        authenticate("ada@example.com", GOOD_PASSWORD, now=NOW)