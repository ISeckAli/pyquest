"""
Tests for the admin pages (spec FR13, PR-M1): access, the user list, and
the actions on a user's page.
"""

import pytest

from app.extensions import db
from app.models import Person, RoleType, UserAccount
from app.services.guest import create_guest


def make_account(email, *roles):
    person = Person(display_name=email.split("@")[0].title(), email=email)
    for role in roles:
        person.add_role(role)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account])
    db.session.commit()
    return account


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


@pytest.fixture
def admin(client):
    account = make_account("admin@example.com", RoleType.SYSTEM_ADMINISTRATOR)
    sign_in(client, account)
    return account


@pytest.fixture
def ada(app):
    return make_account("ada@example.com", RoleType.LEARNER)


def user_url(account, action=""):
    return f"/admin/users/{account.party_id}{action}"


def test_only_administrators_can_open_admin_pages(client):
    assert client.get("/admin/users").status_code == 302  # visitors: to login

    sign_in(client, make_account("teach@example.com", RoleType.INSTRUCTOR))
    assert client.get("/admin/users").status_code == 403


def test_user_list_searches_and_hides_guests(client, admin, ada):
    make_account("grace@example.com", RoleType.LEARNER)
    create_guest()

    everyone = client.get("/admin/users").get_data(as_text=True)
    search = client.get("/admin/users?q=ada").get_data(as_text=True)
    with_guests = client.get("/admin/users?guests=1").get_data(as_text=True)

    assert "grace@example.com" in everyone and "Guest" not in everyone
    assert "ada@example.com" in search and "grace@example.com" not in search
    assert "guest.pyquest.invalid" in with_guests


def test_granting_and_removing_a_role(client, admin, ada):
    response = client.post(user_url(ada, "/roles"), data={"role": "instructor"})
    assert response.headers["Location"] == user_url(ada)
    assert ada.has_role(RoleType.INSTRUCTOR)

    client.post(user_url(ada, "/roles/instructor/revoke"))
    db.session.expire_all()
    assert not ada.has_role(RoleType.INSTRUCTOR)


def test_an_unknown_role_is_a_bad_request(client, admin, ada):
    assert client.post(user_url(ada, "/roles"), data={"role": "wizard"}).status_code == 400


def test_deactivating_and_reactivating_an_account(client, admin, ada):
    client.post(user_url(ada, "/status"), data={"active": "0"})
    db.session.expire_all()
    assert not ada.is_active

    client.post(user_url(ada, "/status"), data={"active": "1"})
    db.session.expire_all()
    assert ada.is_active


def test_admins_are_stopped_from_deactivating_themselves(client, admin):
    response = client.post(user_url(admin, "/status"), data={"active": "0"}, follow_redirects=True)

    assert b"cannot deactivate your own account" in response.data
    db.session.expire_all()
    assert admin.is_active


def test_user_page_shows_history(client, admin, ada):
    client.post(user_url(ada, "/roles"), data={"role": "instructor"})

    html = client.get(user_url(ada)).get_data(as_text=True)

    assert "Role granted: instructor" in html
    assert "by Admin" in html


def test_header_shows_admin_link_only_to_administrators(client, admin, ada):
    assert 'href="/admin/users"' in client.get("/").get_data(as_text=True)

    sign_in(client, ada)
    assert 'href="/admin/users"' not in client.get("/").get_data(as_text=True)


def test_unknown_user_is_not_found(client, admin):
    assert client.get("/admin/users/99999").status_code == 404