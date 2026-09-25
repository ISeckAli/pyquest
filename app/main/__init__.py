"""
Main blueprint: general pages that belong to no specific feature, such as the
home page and the health check.

Every feature area of PyQuest (authentication, challenges, administration,
and so on) lives in its own blueprint. Each blueprint is a self-contained
group of routes and templates, registered with the application in the
factory. This keeps any single file small and lets features be developed and
tested independently, in line with the modularity requirement in the SRS
(NFR07).
"""

from flask import Blueprint

# "main" is the blueprint's name. Flask uses it to build URLs in templates:
# url_for("main.index") refers to the index view in this blueprint.
bp = Blueprint("main", __name__)

# Imported at the bottom on purpose. routes.py attaches its views to `bp`, so
# `bp` must exist before routes.py is loaded. Importing it at the top of this
# file would create a circular import. The noqa comment tells linters this
# placement is intentional.
from app.main import routes  # noqa: E402, F401