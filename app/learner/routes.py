"""
Views for signed-in learners.
"""

from dataclasses import asdict
from datetime import UTC, datetime

from flask import render_template
from flask_login import current_user

from app.auth.decorators import role_required
from app.extensions import db
from app.learner import bp
from app.models import LearnerProfile, RoleType
from app.services.gamification import BADGES, displayed_streak, earned_badges
from app.services.grading import LEVEL_XP_STEP
from app.services.missions import describe, todays_missions


def _level_progress(total_xp, level):
    """How far the learner is through their current level.

    Uses the same formula as level_for_xp() in grading.py: reaching level
    n + 1 from level n costs LEVEL_XP_STEP * n XP.
    """
    start = LEVEL_XP_STEP * (level - 1) * level // 2
    end = LEVEL_XP_STEP * level * (level + 1) // 2
    percent = int(100 * (total_xp - start) / (end - start)) if end > start else 100
    return {
        "next_level": level + 1,
        "xp_to_next": max(0, end - total_xp),
        "percent": max(0, min(100, percent)),
    }


@bp.route("/dashboard")
@role_required(RoleType.LEARNER)
def dashboard():
    """The learner's home page (spec FR14, FR07 to FR10).

    Shows level and progress to the next level, XP, the current and longest
    streak, today's missions, and the badge collection. Visiting creates
    today's missions if they do not exist yet. Charts and Coach progress
    summaries are added in Part 10.
    """
    now = datetime.now(UTC)
    person = current_user.party

    profile = person.learner_profile
    if profile is None:
        # A learner role granted from the command line has no profile yet.
        profile = LearnerProfile(
            person=person, total_xp=0, level=1, current_streak=0, longest_streak=0
        )
        db.session.add(profile)
        db.session.commit()

    earned = earned_badges(current_user)
    earned_codes = {badge["code"] for badge in earned}

    return render_template(
        "learner/dashboard.html",
        profile=profile,
        progress=_level_progress(profile.total_xp, profile.level),
        streak=displayed_streak(profile, person, now),
        missions=[describe(mission) for mission in todays_missions(current_user, now)],
        earned=earned,
        # Locked badges show what to aim for next. Per-topic badges appear
        # once earned, since their list depends on the topics that exist.
        locked=[asdict(badge) for code, badge in BADGES.items() if code not in earned_codes],
    )