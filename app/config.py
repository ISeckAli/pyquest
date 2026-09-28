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

Values marked (tunable) in the product specification live here, so they can
be changed in one place instead of being scattered through the code.
"""

import os
from datetime import timedelta

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

    # --- Session security (spec NFR03 and PR-A2) -----------------------------

    # Sessions end after 30 minutes without activity. Flask re-issues the
    # session cookie on every request by default, so the 30 minutes restart
    # each time the user does something: an inactivity timeout, not a fixed
    # session length.
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # HttpOnly stops page scripts from reading the session cookie, so a
    # cross-site scripting bug could not be used to steal a session.
    SESSION_COOKIE_HTTPONLY = True

    # Lax stops the cookie being sent with requests started by other websites
    # (such as a hidden form on another site), while still allowing normal
    # links to PyQuest to arrive signed in. A second layer beside CSRF tokens.
    SESSION_COOKIE_SAMESITE = "Lax"

    # --- Authentication rules (spec FR01 and FR02, tunable) ------------------

    PASSWORD_MIN_LENGTH = 10
    LOGIN_MAX_FAILED_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15

    # --- Challenge rules (spec FR07, FR12, tunable) --------------------------

    # Default XP for a challenge of each difficulty. Instructors may set a
    # different value per challenge; this is used when they leave it blank.
    CHALLENGE_XP_BY_DIFFICULTY = {"beginner": 10, "intermediate": 25, "advanced": 50}

    # A challenge cannot be published without at least this many test cases
    # of each kind. Hidden tests stop learners from passing by printing the
    # expected output of the examples they can see.
    CHALLENGE_MIN_VISIBLE_TESTS = 1
    CHALLENGE_MIN_HIDDEN_TESTS = 2

    # Instructor-written hints used when the AI Coach is unavailable (NFR05).
    CHALLENGE_MAX_FALLBACK_HINTS = 3

    # --- AI Coach (spec section 5.9, section 11, DR-02) ----------------------

    # Which provider app/services/ai_service.py uses: "gemini", "fake" (tests
    # only), or anything else to switch AI off. Off by default, so a fresh
    # checkout with no key still runs; every Coach feature then falls back
    # to instructor-written content.
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "disabled")

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

    # The Gemini model to use. Google renames and retires models over time,
    # so this can be changed in .env without touching code. Pick one listed
    # as available on the free tier in Google AI Studio.
    AI_MODEL = os.environ.get("AI_MODEL", "gemini-3.8-flash")

    # Seconds to wait for a reply before falling back. The spec's original
    # figure was 8 (FR11), but Gemini rejects any request that allows less
    # than 10 seconds, so 10 is the practical minimum.
    AI_TIMEOUT_SECONDS = 10


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

    # Most tests submit forms directly, so CSRF tokens are switched off here
    # to keep them focused on the behaviour under test. A dedicated test
    # turns CSRF back on to prove forms reject requests without a token.
    WTF_CSRF_ENABLED = False

    # Tests never call a real AI: no network needed, no quota used, and the
    # fake provider records exactly what would have been sent.
    AI_PROVIDER = "fake"


class ProductionConfig(Config):
    """The deployed application."""

    DEBUG = False

    # No fallbacks: a missing value must stop the app from starting rather
    # than silently running with an insecure key or no database.
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    # Only send the session cookie over HTTPS. Not set in development, where
    # the local server uses plain HTTP and the cookie would never be sent.
    SESSION_COOKIE_SECURE = True


# Maps the names used by the application factory to the classes above, so
# the environment is chosen with a plain string such as "testing".
config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}