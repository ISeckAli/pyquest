"""
Flask extension instances.

Each extension is created here once, unbound to any application. The
application factory (app/__init__.py) binds them to an app by calling
init_app(). Keeping creation and binding separate has two benefits:

1. Tests can build a fresh app per test while sharing these same objects.
2. Other modules, such as database models, can import `db` from here without
   importing the application itself, which avoids circular imports.
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# The database handle: defines models, runs queries, and manages sessions.
# SQLAlchemy translates Python code into SQL for whichever database the active
# configuration points to (SQLite locally, Postgres in production), which is
# why no database-specific SQL is written anywhere in the project.
db = SQLAlchemy()

# Schema migrations: records every change to the database structure as a
# versioned script, so the local and production databases can be brought to
# the same structure reliably instead of being edited by hand.
migrate = Migrate()