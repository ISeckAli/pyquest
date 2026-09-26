"""
Tests for the account settings page (spec PR-A5).

The page holds two forms with prefixed field names ("profile-...",
"password-..."), so submissions here use those names, exactly as a browser
would send them.
"""

import re

from sqlalchemy import select

from app.extensions import db
from app.models import Person, RoleType, UserAccount

GOOD_PASSWORD = "violet-harbour-42"
NEW_PASSWORD = "copper-lantern-77"


def register(client):
    return client.post(
        "/register",
        data={
            "display_name": "Ada",
            "email": "ada@example.com",
            "password": GOOD_PASSWORD,
            "confirm_password": GOOD_PASSWORD,
        },
    )


def save_profile(client, display_name="Ada", timezone="America/Toronto", visible=True):
    """Submit the profile form. An unticked checkbox is simply left out,
    which is how browsers send it."""
    data = {
        "profile-display_name": display_name,
        "profile-timezone": timezone,
        "profile-submit": "Save profile",
    }
    if visible:
        data["profile-leaderboard_visible"] = "y"
    return client.post("/settings", data=data)


def change_password(client, current, new, confirm=None):
    return client.post(
        "/settings",
        data={
            "password-current_password": current,
            "password-new_password": new,
            "password-confirm_new_password": confirm if confirm is not None else new,
            "password-submit": "Change password",
        },
    )


def stored_person():
    """Read the person back from the database, not from memory."""
    db.session.expire_all()
    return db.session.scalars(select(Person)).one()


def option_is_selected(html, value):
    """Return True if the <option> with this value is marked selected.

    HTML attribute order carries no meaning, and WTForms writes attributes
    alphabetically (selected before value), so the pattern accepts either
    order instead of depending on one exact spelling of the tag.
    """
    escaped = re.escape(value)
    pattern = (
        rf'<option[^>]*\bselected\b[^>]*\bvalue="{escaped}"'
        rf'|<option[^>]*\bvalue="{escaped}"[^>]*\bselected\b'
    )
    return re.search(pattern, html) is not None


def test_settings_require_login(client):
    response = client.get("/settings")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_settings_page_shows_current_values(client):
    register(client)

    response = client.get("/settings")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Signed in as ada@example.com" in html
    assert option_is_selected(html, "America/Toronto")
    assert not option_is_selected(html, "Europe/London")


def test_saving_profile_updates_all_settings(client):
    register(client)

    response = save_profile(
        client, display_name="Ada L.", timezone="Europe/London", visible=False
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/settings"
    person = stored_person()
    assert person.display_name == "Ada L."
    assert person.timezone == "Europe/London"
    assert person.leaderboard_visible is False


def test_unknown_timezone_is_rejected_and_nothing_changes(client):
    register(client)

    response = save_profile(client, timezone="Mars/Olympus_Mons")

    assert response.status_code == 200
    assert stored_person().timezone == "America/Toronto"


def test_changing_password_lets_user_log_in_with_new_one(client):
    register(client)

    response = change_password(client, GOOD_PASSWORD, NEW_PASSWORD)
    assert response.headers["Location"] == "/settings"

    client.post("/logout")
    login = client.post(
        "/login", data={"email": "ada@example.com", "password": NEW_PASSWORD}
    )
    assert login.headers["Location"] == "/dashboard"


def test_wrong_current_password_is_shown_beside_its_field(client):
    register(client)

    response = change_password(client, "not-my-password-1", NEW_PASSWORD)

    assert response.status_code == 200
    assert b"Current password is incorrect." in response.data


def test_settings_open_to_accounts_without_learner_role(client):
    """Everyone manages their own settings, whatever their role."""
    person = Person(display_name="Staff", email="staff@example.com")
    person.add_role(RoleType.INSTRUCTOR)
    account = UserAccount(party=person)
    account.set_password(GOOD_PASSWORD)
    db.session.add_all([person, account])
    db.session.commit()

    client.post("/login", data={"email": "staff@example.com", "password": GOOD_PASSWORD})

    assert client.get("/settings").status_code == 200