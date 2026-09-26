"""
Tests for the account settings service (spec PR-A5).
"""

import pytest

from app.extensions import db
from app.models import UserAccount
from app.services.account import (
    AccountSettingsError,
    change_password,
    timezone_choices,
    update_profile,
)
from app.services.auth import register_learner

GOOD_PASSWORD = "violet-harbour-42"
NEW_PASSWORD = "copper-lantern-77"


@pytest.fixture
def account(app):
    """A registered learner's account, ready to change settings."""
    return register_learner("Ada", "ada@example.com", GOOD_PASSWORD)


def reload(account):
    """Read the account back from the database, not from memory."""
    db.session.expire_all()
    return db.session.get(UserAccount, account.id)


# ---------------------------------------------------------------------------
# Profile details
# ---------------------------------------------------------------------------

def test_update_profile_saves_all_three_settings(account):
    update_profile(account, "  Ada L.  ", "Europe/London", leaderboard_visible=False)

    person = reload(account).party

    assert person.display_name == "Ada L."
    assert person.timezone == "Europe/London"
    assert person.leaderboard_visible is False


def test_update_profile_rejects_bad_display_name_and_changes_nothing(account):
    with pytest.raises(AccountSettingsError) as error:
        update_profile(account, "A", "Europe/London", leaderboard_visible=False)

    person = reload(account).party

    assert error.value.field == "display_name"
    assert person.display_name == "Ada"
    assert person.timezone == "America/Toronto"


def test_update_profile_rejects_unknown_timezone(account):
    with pytest.raises(AccountSettingsError) as error:
        update_profile(account, "Ada", "Mars/Olympus_Mons", leaderboard_visible=True)

    assert error.value.field == "timezone"


def test_timezone_choices_include_real_zones_in_order(app):
    """Also proves the timezone database is installed on this machine."""
    choices = timezone_choices()

    assert "America/Toronto" in choices
    assert choices == sorted(choices)


# ---------------------------------------------------------------------------
# Password changes
# ---------------------------------------------------------------------------

def test_change_password_replaces_the_old_one(account):
    change_password(account, GOOD_PASSWORD, NEW_PASSWORD)

    stored = reload(account)

    assert stored.check_password(NEW_PASSWORD) is True
    assert stored.check_password(GOOD_PASSWORD) is False


def test_change_password_requires_the_current_password(account):
    with pytest.raises(AccountSettingsError) as error:
        change_password(account, "not-my-password-1", NEW_PASSWORD)

    assert error.value.field == "current_password"
    assert reload(account).check_password(GOOD_PASSWORD) is True


def test_change_password_applies_signup_rules(account):
    with pytest.raises(AccountSettingsError) as error:
        change_password(account, GOOD_PASSWORD, "Password123")

    assert error.value.field == "new_password"
    assert "too common" in str(error.value)


def test_change_password_rejects_reusing_the_current_password(account):
    with pytest.raises(AccountSettingsError) as error:
        change_password(account, GOOD_PASSWORD, GOOD_PASSWORD)

    assert error.value.field == "new_password"