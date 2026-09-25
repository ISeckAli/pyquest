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

from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    """Provide a fresh application configured for testing.

    The code before `yield` runs before the test (setup); the code after it
    runs once the test finishes, even if the test failed (teardown).
    """
    app = create_app("testing")

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