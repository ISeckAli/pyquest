"""
Challenges blueprint: the public challenge library and challenge pages
(spec FR04, PR-L1).

Browsing is open to everyone, including visitors who are not signed in
(spec section 4.2), so these routes do not require login. Solving a
challenge and earning XP arrive in Part 6.
"""

from flask import Blueprint

bp = Blueprint("challenges", __name__)

# Imported at the bottom on purpose: routes.py attaches its views to `bp`,
# so `bp` must exist first.
from app.challenges import routes  # noqa: E402, F401