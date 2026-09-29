"""
Tests for the error pages and favicon (spec PR-N2, NFR06).
"""

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount

WRONG_LOGIN = {"email": "nobody@example.com", "password": "not-the-password"}


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


def test_a_missing_page_gets_a_friendly_404(client):
    response = client.get("/no-such-page")

    assert response.status_code == 404
    assert b"Page not found" in response.data
    assert b"Go to the home page" in response.data


def test_api_errors_stay_json(client):
    response = client.get("/api/no-such-endpoint")

    assert response.status_code == 404
    assert "error" in response.get_json()


def test_forbidden_pages_get_a_friendly_403(client):
    sign_in(client, make_learner())

    response = client.get("/admin/users")

    assert response.status_code == 403
    assert b"Access denied" in response.data


def test_rate_limited_pages_get_a_friendly_429_with_retry_after(client):
    for _ in range(10):
        client.post("/login", data=WRONG_LOGIN)

    response = client.post("/login", data=WRONG_LOGIN)

    assert response.status_code == 429
    assert b"Slow down a little" in response.data
    assert "Retry-After" in response.headers


def test_an_expired_form_explains_what_to_do(app, client):
    app.config["WTF_CSRF_ENABLED"] = True

    response = client.post("/login", data=WRONG_LOGIN)

    assert response.status_code == 400
    assert b"This form expired" in response.data


def test_unexpected_errors_show_an_apology_without_details(app, client):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/explode")
    def explode():
        raise RuntimeError("secret internal detail")

    response = client.get("/explode")

    assert response.status_code == 500
    assert b"Something went wrong" in response.data
    assert b"secret internal detail" not in response.data
    assert b"RuntimeError" not in response.data


def test_the_favicon_is_linked_and_the_old_name_redirects(client):
    assert b'rel="icon"' in client.get("/").data

    response = client.get("/favicon.ico")

    assert response.status_code == 301
    assert response.headers["Location"].endswith("/static/favicon.svg")