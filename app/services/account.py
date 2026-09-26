"""
Account settings service: profile details and password changes (spec PR-A5).

Kept separate from the authentication service (registration and login),
but reuses its password rules, so a new password must meet exactly the
same standard as one chosen at sign-up.
"""

from zoneinfo import available_timezones

from app.extensions import db
from app.services.auth import (
    DISPLAY_NAME_MAX_LENGTH,
    DISPLAY_NAME_MIN_LENGTH,
    RegistrationError,
    validate_password,
)

# Every timezone name in the IANA database, such as "America/Toronto".
# Loaded once when the module is imported. On Windows this list comes from
# the tzdata package (listed in requirements.txt); Linux and macOS provide
# it themselves.
VALID_TIMEZONES = frozenset(available_timezones())


class AccountSettingsError(Exception):
    """A settings change was rejected. The message is safe to show.

    Attributes:
        field: the form field the message belongs to, so the page can show
            it beside the right input.
    """

    def __init__(self, message, field):
        super().__init__(message)
        self.field = field


def timezone_choices():
    """Return every valid timezone name in alphabetical order, for a menu."""
    return sorted(VALID_TIMEZONES)


def update_profile(account, display_name, timezone, leaderboard_visible):
    """Change a person's display name, timezone, and leaderboard visibility.

    All inputs are checked before anything is changed, so a rejected update
    leaves the profile exactly as it was.

    Raises:
        AccountSettingsError: if the display name or timezone is invalid.
    """
    display_name = display_name.strip()

    if not DISPLAY_NAME_MIN_LENGTH <= len(display_name) <= DISPLAY_NAME_MAX_LENGTH:
        raise AccountSettingsError(
            f"Display name must be {DISPLAY_NAME_MIN_LENGTH} to "
            f"{DISPLAY_NAME_MAX_LENGTH} characters long.",
            "display_name",
        )

    # Checked against the real timezone list, because streaks and daily
    # missions later use this value to decide when a learner's day starts;
    # a misspelled zone would break those calculations.
    if timezone not in VALID_TIMEZONES:
        raise AccountSettingsError("Choose a timezone from the list.", "timezone")

    person = account.party
    person.display_name = display_name
    person.timezone = timezone
    person.leaderboard_visible = bool(leaderboard_visible)
    db.session.commit()


def change_password(account, current_password, new_password):
    """Replace a password after confirming the current one.

    Requiring the current password means someone who finds a signed-in
    computer left unattended cannot lock the owner out of their account.

    Raises:
        AccountSettingsError: if the current password is wrong, or the new
            one breaks the password rules or matches the current one.
    """
    if not account.check_password(current_password):
        raise AccountSettingsError("Current password is incorrect.", "current_password")

    if new_password == current_password:
        raise AccountSettingsError(
            "New password must be different from your current password.",
            "new_password",
        )

    try:
        validate_password(new_password, email=account.party.email)
    except RegistrationError as error:
        # Same rules as sign-up; only the field name differs on this form.
        raise AccountSettingsError(str(error), "new_password") from error

    account.set_password(new_password)
    db.session.commit()