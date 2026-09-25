"""
Tests for the application factory and the main blueprint.

Test names describe the behaviour they check, so a failing test reads as a
sentence explaining what broke, for example:
    test_health_returns_ok_json FAILED
"""

import pytest

from app import create_app
from app.config import ProductionConfig


# ---------------------------------------------------------------------------
# Main blueprint routes
# ---------------------------------------------------------------------------

def test_index_page_loads(client):
    """The landing page responds successfully and shows the PyQuest headline."""
    response = client.get("/")

    assert response.status_code == 200
    assert b"Learn Python. Earn XP. Unlock Achievements." in response.data


def test_index_page_has_features_section(client):
    """The Features navigation link has a section on the page to scroll to."""
    response = client.get("/")

    assert b'id="features"' in response.data


def test_health_returns_ok_json(client):
    """The health check returns JSON the hosting platform can read."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == {"status": "ok"}


def test_unknown_route_returns_404(client):
    """A URL with no matching route returns Not Found rather than an error."""
    response = client.get("/this-page-does-not-exist")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def test_testing_config_is_applied(app):
    """create_app("testing") enables testing mode with an in-memory database."""
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_unknown_config_name_is_rejected():
    """A misspelled environment name fails loudly instead of guessing."""
    with pytest.raises(ValueError):
        create_app("prodution")


def test_production_refuses_to_start_without_secrets(monkeypatch):
    """Production must not start with no secret key or database configured.

    monkeypatch temporarily blanks the two settings for this test only and
    restores them afterwards. The result is therefore the same on every
    machine, whether or not a local .env file happens to define them.
    """
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", None)
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", None)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")