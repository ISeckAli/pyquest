"""
Views for the main blueprint: public pages that belong to no single
feature area.

Each function below is a view: Flask calls it when a request arrives for the
URL in its @bp.route(...) decorator, and sends its return value back to the
browser as the response.
"""

from flask import jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.main import bp
from app.models import RoleType
from app.services.leaderboard import ALL_TIME, PERIODS, THIS_WEEK, leaderboard


@bp.route("/")
def index():
    """Render the landing page."""
    # render_template looks inside app/templates/, so this loads
    # app/templates/main/index.html. Templates are grouped in a folder named
    # after their blueprint so that pages from different blueprints never
    # collide on the same file name.
    return render_template("main/index.html")


@bp.route("/health")
def health():
    """Report that the application is running.

    The hosting platform requests this URL after each deploy to confirm the
    app started, and uptime monitors can poll it. It returns JSON rather than
    HTML because it is read by programs, not people. It deliberately avoids
    the database and templates, so it answers even if those are
    misconfigured, and the problem can be traced to the right layer.
    """
    return jsonify(status="ok")


@bp.route("/favicon.ico")
def favicon():
    """Point browsers that ask for the old favicon.ico name at the real icon.

    Pages declare the icon in base.html, but some browsers still request
    /favicon.ico directly. A permanent redirect answers them once; the
    browser then remembers it.
    """
    return redirect(url_for("static", filename="favicon.svg"), code=301)


@bp.route("/leaderboard")
def leaderboard_page():
    """The public leaderboard (spec FR09): all time, or this week.

    Open to everyone, since it shows only display names, levels, and XP.
    Signed-in learners see their own row highlighted, or their rank below
    the table if they are outside the top.
    """
    period = request.args.get("period", ALL_TIME)
    if period not in PERIODS:
        period = ALL_TIME

    viewer = current_user if current_user.is_authenticated else None
    top, viewer_standing = leaderboard(period, viewer)

    viewer_hidden = (
        viewer is not None
        and viewer.has_role(RoleType.LEARNER)
        and not viewer.party.leaderboard_visible
    )

    return render_template(
        "main/leaderboard.html",
        period=period,
        periods=[(ALL_TIME, "All time"), (THIS_WEEK, "This week")],
        top=top,
        viewer_standing=viewer_standing,
        viewer_party_id=viewer.party_id if viewer is not None else None,
        viewer_hidden=viewer_hidden,
    )