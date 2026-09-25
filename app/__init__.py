"""
PyQuest application package.

create_app() is an application factory: rather than creating one global
Flask app when this module is imported, it builds and configures a new app
each time it is called. This lets the same code run with different settings:

    create_app()               development settings (the default)
    create_app("testing")      in-memory database, used by pytest
    FLASK_CONFIG=production    deployed settings, selected by the host

The Flask command line finds this function automatically, so the app is
started with `flask --app app run`.
"""

import os

from flask import Flask

from app.config import config_by_name
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_name=None):
    """Build and return a configured Flask application.

    Args:
        config_name: "development", "testing", or "production". When omitted,
            the FLASK_CONFIG environment variable decides, falling back to
            "development" so a fresh checkout runs with no extra setup.

    Raises:
        ValueError: if config_name is not a known environment.
        RuntimeError: if production settings are missing required secrets.
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG", "development")

    config_class = config_by_name.get(config_name)
    if config_class is None:
        valid = ", ".join(sorted(config_by_name))
        raise ValueError(f"Unknown config '{config_name}'. Expected one of: {valid}.")

    app = Flask(__name__)
    app.config.from_object(config_class)

    if config_name == "production":
        _require_production_settings(app)

    # Bind the shared extension objects to this specific app instance.
    db.init_app(app)

    # render_as_batch makes migrations work on SQLite, which cannot alter an
    # existing table in place (for example to drop or rename a column).
    # Batch mode copies the table, applies the change, and swaps it in.
    # Postgres does not need this, but it is harmless there, so the same
    # migration scripts run on both databases.
    migrate.init_app(app, db, render_as_batch=True)

    login_manager.init_app(app)
    csrf.init_app(app)

    # Importing the models package registers every table with SQLAlchemy.
    # Without this import, migrations would not see the models and
    # db.create_all() in the tests would create no tables. It also registers
    # the Flask-Login user loader defined alongside UserAccount.
    from app import models  # noqa: F401

    _register_blueprints(app)

    return app


def _register_blueprints(app):
    """Attach every feature blueprint to the application.

    Blueprints are imported inside this function rather than at the top of
    the module. As features are added, blueprints import models, and models
    import `db`; importing blueprints only once the app is being built keeps
    that chain from looping back on itself (a circular import).
    """
    from app.main import bp as main_bp

    app.register_blueprint(main_bp)


def _require_production_settings(app):
    """Stop the app from starting in production with missing secrets.

    A clear error at startup is far easier to diagnose than a live site that
    runs with no database or an unsigned session cookie.
    """
    missing = [
        name
        for name in ("SECRET_KEY", "SQLALCHEMY_DATABASE_URI")
        if not app.config.get(name)
    ]
    if missing:
        raise RuntimeError(
            "Production is missing required settings: "
            + ", ".join(missing)
            + ". Set SECRET_KEY and DATABASE_URL in the hosting environment."
        )