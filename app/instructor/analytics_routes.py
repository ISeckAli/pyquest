"""
Instructor analytics page (spec FR15). Kept apart from routes.py, which
handles writing and publishing challenges; both attach to the instructor
blueprint.
"""

from flask import render_template
from flask_login import current_user

from app.auth.decorators import role_required
from app.instructor import bp
from app.models import RoleType
from app.services.instructor_analytics import (
    LOW_SOLVE_RATE,
    MIN_LEARNERS_FOR_FLAG,
    challenge_stats,
)


@bp.route("/analytics")
@role_required(RoleType.INSTRUCTOR, RoleType.SYSTEM_ADMINISTRATOR)
def analytics():
    """How each challenge the account manages is going for learners."""
    return render_template(
        "instructor/analytics.html",
        stats=challenge_stats(current_user),
        min_learners=MIN_LEARNERS_FOR_FLAG,
        low_rate=LOW_SOLVE_RATE,
        is_admin=current_user.has_role(RoleType.SYSTEM_ADMINISTRATOR),
    )