"""
API blueprint: JSON endpoints used by the challenge page's JavaScript.

Pages return HTML; these return JSON, including for errors (401, 403, 404,
400), so the browser code can always read the response the same way.

POST requests still need a CSRF token. The page's JavaScript sends it in an
X-CSRFToken header, which Flask-WTF checks automatically (spec PR-N2).
"""

from flask import Blueprint

bp = Blueprint("api", __name__, url_prefix="/api")

# Imported at the bottom on purpose: routes.py attaches its views to `bp`,
# so `bp` must exist first.
from app.api import routes  # noqa: E402, F401