"""
Learner blueprint: pages for signed-in learners, starting with the
dashboard (spec FR14). Grows in later parts to hold progress, analytics,
and AI Coach summaries.
"""

from flask import Blueprint

bp = Blueprint("learner", __name__)

# Imported at the bottom on purpose: routes.py attaches its views to `bp`,
# so `bp` must exist first.
from app.learner import routes  # noqa: E402, F401