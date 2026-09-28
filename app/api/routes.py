"""
JSON endpoints for running, saving, and submitting challenges (spec FR05,
FR06), and for instructors checking a reference solution (FR12).
"""

from functools import wraps

from flask import jsonify, request
from flask_login import current_user

from app.api import bp
from app.extensions import db
from app.models import Challenge, RoleType
from app.services.challenges import can_manage, get_published
from app.services.grading import GradingError, grade_submission, runnable_tests
from app.services.workspace import WorkspaceError, save_code


def api_role_required(*role_types):
    """Like role_required, but answers in JSON instead of redirecting.

    A browser script calling the API needs a clear status code it can act
    on (401: sign in; 403: not allowed), not a redirect to an HTML login
    page it cannot use.
    """

    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify(error="Log in to continue."), 401
            if not any(current_user.has_role(role) for role in role_types):
                return jsonify(error="You do not have access to this."), 403
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def _not_found():
    return jsonify(error="Challenge not found."), 404


def _json_payload():
    """The request body as a dictionary, or None if it is not a JSON object.

    silent=True returns None instead of raising for a body that is not
    valid JSON, so every malformed request gets the same clear 400.
    """
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else None


@bp.route("/challenges/<slug>/tests")
@api_role_required(RoleType.LEARNER)
def challenge_tests(slug):
    """The tests the browser runs the learner's code against.

    Signed-in learners only, so hidden test inputs are not handed to anyone
    who simply visits the page. Hidden expected outputs are never included.
    """
    challenge = get_published(slug)
    if challenge is None:
        return _not_found()
    return jsonify(runnable_tests(challenge))


@bp.route("/challenges/<slug>/code", methods=["PUT"])
@api_role_required(RoleType.LEARNER)
def save_workspace_code(slug):
    """Save the learner's working copy of their code (spec FR05).

    PUT, because each save replaces the previous copy rather than adding a
    new record.
    """
    challenge = get_published(slug)
    if challenge is None:
        return _not_found()

    payload = _json_payload()
    if payload is None:
        return jsonify(error="Send the code as JSON."), 400

    try:
        save_code(current_user, challenge, payload.get("code"))
    except WorkspaceError as error:
        return jsonify(error=str(error)), 400

    return jsonify(saved=True)


@bp.route("/challenges/<slug>/submissions", methods=["POST"])
@api_role_required(RoleType.LEARNER)
def submit(slug):
    """Grade a submission and return feedback (spec FR06)."""
    challenge = get_published(slug)
    if challenge is None:
        return _not_found()

    payload = _json_payload()
    if payload is None:
        return jsonify(error="Send the submission as JSON."), 400

    try:
        _, feedback = grade_submission(
            current_user,
            challenge,
            payload.get("code"),
            payload.get("results"),
            payload.get("execution_ms"),
        )
    except GradingError as error:
        return jsonify(error=str(error)), 400

    return jsonify(feedback)


@bp.route("/instructor/challenges/<int:challenge_id>/reference-check")
@api_role_required(RoleType.INSTRUCTOR, RoleType.SYSTEM_ADMINISTRATOR)
def reference_check(challenge_id):
    """The reference solution and every test with its expected output.

    The only endpoint that sends hidden expected outputs to a browser, so it
    is limited to accounts that may manage this particular challenge: its
    author or an administrator. It works for drafts too, since the check is
    meant to run before publishing.
    """
    challenge = db.session.get(Challenge, challenge_id)
    if challenge is None:
        return _not_found()
    if not can_manage(current_user, challenge):
        return jsonify(error="You do not have access to this."), 403

    return jsonify(
        code=challenge.reference_solution,
        tests=[
            {
                "id": test.id,
                "input": test.input_data,
                "expected": test.expected_output,
                "hidden": test.is_hidden,
            }
            for test in challenge.test_cases
        ],
    )