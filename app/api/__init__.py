"""
API blueprint: JSON endpoints used by the challenge page's JavaScript.

Pages return HTML; these return JSON, including for errors (401, 403, 404,
400, 429), so the browser code can always read the response the same way.

POST requests still need a CSRF token. The page's JavaScript sends it in an
X-CSRFToken header, which Flask-WTF checks automatically (spec PR-N2).

Routes are split across files by area: routes.py (running, saving,
submitting, hints, explanations, reference checks) and coach_routes.py
(chat, reviews, ratings).
"""

from flask import Blueprint

bp = Blueprint("api", __name__, url_prefix="/api")

# Imported at the bottom on purpose: the route modules attach their views
# to `bp`, so `bp` must exist first.
from app.api import coach_routes, routes  # noqa: E402, F401