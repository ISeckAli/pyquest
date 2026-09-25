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
from sqlalchemy import MetaData

# Predictable names for database constraints (primary keys, foreign keys,
# unique rules, indexes, checks). Without this, some databases generate
# random names, and later migrations cannot reliably find a constraint to
# alter or drop it. Defining the convention before the first table exists
# means every constraint in the project follows it.
#
# Unique rules use column_0_N_name, which joins the names of every column in
# the rule, so a rule spanning several columns says so in its name. Example
# results: "uq_person_email" for one column, "uq_role_party_id_role_type"
# for the rule that a party can hold each role only once.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# The database handle: defines models, runs queries, and manages sessions.
# SQLAlchemy translates Python code into SQL for whichever database the active
# configuration points to (SQLite locally, Postgres in production), which is
# why no database-specific SQL is written anywhere in the project.
db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))

# Schema migrations: records every change to the database structure as a
# versioned script, so the local and production databases can be brought to
# the same structure reliably instead of being edited by hand.
migrate = Migrate()