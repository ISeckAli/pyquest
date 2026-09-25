"""
Application configuration.

Settings are grouped into one class per environment. The application
factory (app/__init__.py) selects a class by name, so the same codebase runs
locally, under test, and in production with no code changes: only the
environment variables differ.

Secrets and machine-specific values (secret key, database URL, API keys) are
read from environment variables instead of being written in this file. Locally
they come from a git-ignored .env file; in production the hosting platform
supplies them. This keeps secrets out of the public repository.
"""

import os

from dotenv import load_dotenv

# Load variables from .env into the environment before the classes below read
# them. Class attributes are evaluated once, when this module is first
# imported, so loading must happen here rather than later inside the factory.
# load_dotenv() never overwrites variables that already exist, so values set
# by the hosting platform in production always take priority over any .env.
load_dotenv()


class Config:
    """Settings shared by every environment."""

    # Signs session cookies so users cannot tamper with them. Development
    # falls back to a fixed placeholder so the app starts with no setup.
    # ProductionConfig overrides this with no fallback, and the application
    # factory refuses to start production without a real key.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")

    # Modification tracking powers an event system this project does not use,
    # and it costs extra memory, so it is turned off.
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    """Local development on a developer's machine."""

    DEBUG = True

    # Flask-SQLAlchemy places a relative SQLite path inside Flask's instance/
    # folder, which Git ignores. Setting DATABASE_URL overrides this, for
    # example to develop against a Postgres database before deploying.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///pyquest.db")


class TestingConfig(Config):
    """Automated test runs, both locally and in CI."""

    TESTING = True

    # A fixed key keeps test results identical on every machine.
    SECRET_KEY = "test-secret-key"

    # An in-memory database is created fresh for each test and discarded
    # afterwards, so tests never touch development data and never depend on
    # data left behind by another test.
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    """The deployed application."""

    DEBUG = False

    # No fallbacks: a missing value must stop the app from starting rather
    # than silently running with an insecure key or no database.
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


# Maps the names used by the application factory to the classes above, so
# the environment is chosen with a plain string such as "testing".
config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}