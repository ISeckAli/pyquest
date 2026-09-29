"""
Error pages (spec PR-N2, NFR06): friendly, styled pages instead of the
server's plain defaults, and JSON for the API.

Visitors never see technical details. An unexpected error rolls back the
unfinished database change, is logged in full for the developer, and shows
a plain apology.
"""

from flask import current_app, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from app.extensions import db

# status: (page title, message). Statuses not listed keep their defaults.
PAGES = {
    400: ("Something was not quite right", "That request did not look right. Please go back and try again."),
    403: ("Access denied", "You do not have permission to view this page."),
    404: ("Page not found", "We could not find that page. It may have moved, or the address may have a typo."),
    405: ("Not allowed", "That action is not available here. Please go back and try again."),
    429: ("Slow down a little", "Too many requests. Please wait a moment and try again."),
}

CSRF_MESSAGE = "This form expired. Go back, refresh the page, and try again."
SERVER_ERROR_MESSAGE = "Something went wrong on our side. Please try again in a moment."


def _wants_json():
    """API requests get JSON errors; everything else gets a page."""
    return request.path.startswith("/api/")


def error_response(status, message=None, retry_after=None):
    """A styled error page, or JSON for the API, with the given status."""
    title, default_message = PAGES[status]
    message = message or default_message

    if _wants_json():
        response = jsonify(error=message)
        response.status_code = status
    else:
        response = current_app.make_response(
            (render_template("errors/error.html", status=status, title=title, message=message), status)
        )

    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


def register_error_handlers(app):
    """Attach PyQuest's error pages to the app."""

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        # Usually a tab left open past the session timeout: the form's
        # security token is no longer valid.
        return error_response(400, CSRF_MESSAGE)

    @app.errorhandler(HTTPException)
    def http_error(error):
        if error.code in PAGES:
            return error_response(error.code)
        return error

    @app.errorhandler(Exception)
    def unexpected_error(error):
        # Undo any half-finished database change, so the next request
        # starts clean, and record the full details for the developer.
        db.session.rollback()
        app.logger.exception("Unhandled error on %s %s", request.method, request.path)

        if _wants_json():
            return jsonify(error=SERVER_ERROR_MESSAGE), 500
        # A standalone page: the normal layout loads the signed-in user from
        # the database, which may be exactly what failed.
        return render_template("errors/500.html"), 500