"""
Shared pytest fixtures.

pytest loads this file automatically, so every test in this folder can use
the fixtures below just by naming them as function arguments. For example:

    def test_something(client):
        response = client.get("/")

Every test receives a brand-new application and an empty in-memory database,
so tests are isolated: no test depends on data another test left behind, and
the tests can run in any order.
"""

import pytest
from flask import g

from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    """Provide a fresh application configured for testing.

    The code before `yield` runs before the test (setup); the code after it
    runs once the test finishes, even if the test failed (teardown).
    """
    app = create_app("testing")

    # Flask-Login caches the signed-in user in `g` for the rest of a
    # request. In production every request gets a fresh `g`. In tests,
    # the application context opened below stays open for the whole test
    # (so tests can use the database between requests), and Flask reuses
    # it for each test-client request, so `g` would carry the cached user
    # from one request into the next. Clearing it at the start of each
    # request makes tests behave like production: the signed-in user is
    # always read fresh from the session, which matters whenever a test
    # switches from one user to another.
    @app.before_request
    def _forget_cached_user():
        g.pop("_login_user", None)

    # Database operations need an application context: Flask's way of
    # knowing which app (and therefore which database) is active.
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Provide a test client for making requests without a running server.

    Depends on the `app` fixture, so each client talks to a fresh app.
    """
    return app.test_client()