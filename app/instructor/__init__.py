"""
Instructor blueprint: writing, testing, previewing, and publishing
challenges (spec FR12).

Every route requires the instructor or system administrator role, and
every route that acts on a challenge also checks that the signed-in account
may manage that particular challenge (app/services/challenges.can_manage).
"""

from flask import Blueprint

# url_prefix puts every route in this blueprint under /instructor.
bp = Blueprint("instructor", __name__, url_prefix="/instructor")

# Imported at the bottom on purpose: routes.py attaches its views to `bp`,
# so `bp` must exist first.
from app.instructor import routes  # noqa: E402, F401