"""
Tests for the authentication pages and access control (spec FR01 to FR03,
PR-A2, NFR03, PR-N2).

These drive the app through its URLs with the test client, the way a
browser would, so they check routes, forms, templates, and the auth service
working together.
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import Person, RoleType, UserAccount

GOOD_PASSWORD = "violet-harbour-42"


def register(client, email="ada@example.com", password=GOOD_PASSWORD, confirm=None):
    """Submit the sign-up form. confirm defaults to the same password."""
    return client.post(
        "/register",
        data={
            "display_name": "Ada",
            "email": email,
            "password": password,
            "confirm_password": confirm if confirm is not None else password,
        },
    )


def login(client, email="ada@example.com", password=GOOD_PASSWORD, next_url=None):
    """Submit the login form, optionally with a ?next= target."""
    url = "/login" if next_url is None else f"/login?next={next_url}"
    return client.post(url, data={"email": email, "password": password})


def create_account_with_roles(email, *roles):
    """Create a person with the given roles directly, bypassing sign-up.

    Sign-up always grants the learner role, so this is how tests create
    accounts without it, such as an instructor who is not a learner.
    """
    person = Person(display_name="Staff", email=email)
    for role in roles:
        person.add_role(role)
    account = UserAccount(party=person)
    account.set_password(GOOD_PASSWORD)
    db.session.add_all([person, account])
    db.session.commit()
    return account


# ---------------------------------------------------------------------------
# Registration pages
# ---------------------------------------------------------------------------

def test_register_page_loads(client):
    response = client.get("/register")

    assert response.status_code == 200
    assert b"Start your mission" in response.data


def test_registering_signs_in_and_opens_dashboard(client):
    response = register(client)

    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard"

    dashboard = client.get("/dashboard")
    assert b"Welcome, Ada." in dashboard.data


def test_service_rule_errors_appear_on_the_form(client):
    """A password rule from the service is shown beside the password field."""
    response = register(client, password="short", confirm="short")

    assert response.status_code == 200
    assert b"at least 10 characters" in response.data
    assert db.session.scalar(select(func.count()).select_from(Person)) == 0


def test_mismatched_passwords_are_rejected(client):
    response = register(client, confirm="violet-harbour-99")

    assert b"The passwords do not match." in response.data


# ---------------------------------------------------------------------------
# Login and sessions
# ---------------------------------------------------------------------------

def test_login_redirects_to_dashboard(client):
    register(client)
    client.post("/logout")

    response = login(client)

    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard"


def test_failed_login_shows_generic_message(client):
    register(client)
    client.post("/logout")

    response = login(client, password="wrong-password-123")

    assert response.status_code == 200
    assert b"Email or password is incorrect." in response.data


def test_session_expires_after_thirty_minutes_of_inactivity(client, app):
    """NFR03: the signed-in session is permanent with a 30-minute lifetime."""
    register(client)

    with client.session_transaction() as session:
        assert session.permanent is True
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(minutes=30)


def test_login_returns_user_to_the_page_they_wanted(client):
    register(client)
    client.post("/logout")

    response = login(client, next_url="/dashboard")

    assert response.headers["Location"] == "/dashboard"


@pytest.mark.parametrize(
    "next_url",
    ["https://evil.example", "//evil.example", "/\\evil.example"],
)
def test_login_ignores_next_pointing_to_another_site(client, next_url):
    """Open redirect protection: only paths within PyQuest are followed."""
    register(client)
    client.post("/logout")

    response = login(client, next_url=next_url)

    assert response.headers["Location"] == "/dashboard"


def test_signed_in_user_visiting_login_goes_to_dashboard(client):
    register(client)

    response = client.get("/login")

    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard"


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout_signs_the_user_out(client):
    register(client)

    response = client.post("/logout")

    assert response.headers["Location"] == "/"
    assert client.get("/dashboard").status_code == 302


def test_logout_cannot_be_triggered_by_a_link(client):
    """GET is refused, so a link or image on another site cannot log users out."""
    register(client)

    assert client.get("/logout").status_code == 405


# ---------------------------------------------------------------------------
# Access control (FR03)
# ---------------------------------------------------------------------------

def test_dashboard_sends_visitors_to_login(client):
    response = client.get("/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login?next=")


def test_dashboard_forbidden_to_accounts_without_learner_role(client):
    """An instructor who is not also a learner gets 403, not the page."""
    create_account_with_roles("staff@example.com", RoleType.INSTRUCTOR)
    login(client, email="staff@example.com")

    assert client.get("/dashboard").status_code == 403


def test_deactivated_user_is_signed_out_on_next_request(client):
    """FR13: deactivation takes effect immediately, not at the next login."""
    register(client)
    account = db.session.scalars(select(UserAccount)).one()
    account.is_active = False
    db.session.commit()

    response = client.get("/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_header_shows_logout_only_when_signed_in(client):
    assert b"Log out" not in client.get("/").data

    register(client)

    assert b"Log out" in client.get("/").data


# ---------------------------------------------------------------------------
# CSRF protection (PR-N2)
# ---------------------------------------------------------------------------

def test_forms_reject_submissions_without_a_csrf_token(client, app):
    """With CSRF switched back on, a form posted without its token fails."""
    app.config["WTF_CSRF_ENABLED"] = True

    response = client.post(
        "/login", data={"email": "ada@example.com", "password": GOOD_PASSWORD}
    )

    assert response.status_code == 400