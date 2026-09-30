"""
Tests for the deployment settings (Part 16): the database address
conversion, production connection settings, and the Render Blueprint.
"""

from pathlib import Path

import pytest

from app.config import ProductionConfig, database_url

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgresql://user:pw@host/db?sslmode=require", "postgresql+psycopg://user:pw@host/db?sslmode=require"),
        ("postgres://user:pw@host/db", "postgresql+psycopg://user:pw@host/db"),
        ("postgresql+psycopg://user:pw@host/db", "postgresql+psycopg://user:pw@host/db"),
        ("sqlite:///pyquest.db", "sqlite:///pyquest.db"),
        (None, None),
    ],
)
def test_database_addresses_are_converted_for_sqlalchemy(given, expected):
    assert database_url(given) == expected


def test_production_reconnects_after_the_database_pauses():
    assert ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS["pool_pre_ping"] is True


def test_the_blueprint_migrates_seeds_and_starts_one_gunicorn_worker():
    blueprint = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "flask --app app db upgrade" in blueprint
    assert "flask --app app seed" in blueprint
    assert "gunicorn" in blueprint and "--workers 1" in blueprint
    assert "healthCheckPath: /health" in blueprint
    # Secrets are asked for during setup, never written in the file.
    assert "key: DATABASE_URL\n        sync: false" in blueprint
    assert "key: GEMINI_API_KEY\n        sync: false" in blueprint


def test_the_production_packages_are_listed():
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()

    assert "gunicorn==" in requirements
    assert "psycopg==" in requirements