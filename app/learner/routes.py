"""
Views for signed-in learners.
"""

from flask import render_template
from flask_login import current_user

from app.auth.decorators import role_required
from app.learner import bp
from app.models import RoleType


@bp.route("/dashboard")
@role_required(RoleType.LEARNER)
def dashboard():
    """The learner's home page after login (spec FR14, first version).

    Shows level, XP, and streak from the learner's profile. Charts, badges,
    daily missions, and Coach progress summaries are added in later parts.
    """
    profile = current_user.party.learner_profile
    return render_template("learner/dashboard.html", profile=profile)