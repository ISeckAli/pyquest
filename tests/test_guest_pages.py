"""
Tests for how guest mode appears on the site (spec PR-A3).
"""

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


def make_learner():
    person = Person(display_name="Ada", email="ada@example.com")
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account, LearnerProfile(person=person)])
    db.session.commit()
    return account


def test_landing_page_offers_try_as_guest_to_visitors(client):
    html = client.get("/").get_data(as_text=True)

    assert 'action="/guest"' in html
    assert "Try as Guest" in html


def test_guests_see_the_banner_and_save_progress_instead_of_settings(client):
    client.post("/guest")

    html = client.get("/challenges").get_data(as_text=True)

    assert "exploring as a guest" in html
    assert "Save progress" in html
    assert 'href="/settings"' not in html


def test_real_learners_see_no_guest_banner(client):
    sign_in(client, make_learner())

    html = client.get("/challenges").get_data(as_text=True)

    assert "exploring as a guest" not in html
    assert 'href="/settings"' in html


def test_signed_in_visitors_are_not_offered_guest_mode(client):
    sign_in(client, make_learner())

    assert 'action="/guest"' not in client.get("/").get_data(as_text=True)