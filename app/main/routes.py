"""
Views for the main blueprint.

Each function below is a view: Flask calls it when a request arrives for the
URL in its @bp.route(...) decorator, and sends its return value back to the
browser as the response.
"""

from flask import jsonify, render_template

from app.main import bp


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