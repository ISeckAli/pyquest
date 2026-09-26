"""
Authentication blueprint: registration, login, and logout (spec FR01 to
FR03, PR-A2).

Routes here stay thin: they read the form, call the authentication service
(app/services/auth.py), and turn the result into a page or a redirect.
"""

from flask import Blueprint

bp = Blueprint("auth", __name__)

# Imported at the bottom on purpose: routes.py attaches its views to `bp`,
# so `bp` must exist first. See app/main/__init__.py for the same pattern.
from app.auth import routes  # noqa: E402, F401