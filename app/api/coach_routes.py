"""
JSON endpoints for Ask the Coach, code review, and ratings (spec PR-C3,
PR-C4, PR-C6). Kept separate from routes.py so each file stays focused;
both attach to the same api blueprint.
"""

from flask import jsonify
from flask_login import current_user

from app.api import bp
from app.api.routes import _json_payload, _not_found, api_role_required
from app.models import RoleType
from app.rate_limit import rate_limit
from app.services.challenges import get_published
from app.services.coach import CoachError, CoachLimitError
from app.services.coach_chat import CoachNotFoundError, ask_coach, rate_message, review_solution
from app.services.coach_ratings import rate_hint
from app.services.grading import MAX_CODE_LENGTH
from app.services.guest import GUEST_CHAT_LIMIT, guest_chat_remaining, is_guest


def message_json(message):
    """A Coach message as the page needs it."""
    return {
        "id": message.id,
        "sender": message.sender.value,
        "text": message.content,
        "source": message.source.value,
        "rating": message.rating,
    }


@bp.route("/challenges/<slug>/chat", methods=["POST"])
@api_role_required(RoleType.LEARNER)
@rate_limit("chat")
def chat(slug):
    """Ask the Coach a question about this challenge (PR-C4).

    Guests get a small allowance (spec PR-A3), which protects the free AI
    quota while still letting visitors try the Coach.
    """
    challenge = get_published(slug)
    if challenge is None:
        return _not_found()

    if is_guest(current_user) and guest_chat_remaining(current_user) <= 0:
        return jsonify(
            error=f"Guests can send {GUEST_CHAT_LIMIT} messages. "
            "Create a free account to keep chatting with the Coach."
        ), 429

    payload = _json_payload()
    if payload is None:
        return jsonify(error="Send the message as JSON."), 400

    code = payload.get("code", "")
    if not isinstance(code, str) or len(code) > MAX_CODE_LENGTH:
        return jsonify(error=f"Code must be text of at most {MAX_CODE_LENGTH} characters."), 400

    try:
        learner_message, coach_message = ask_coach(
            current_user, challenge, payload.get("message"), code
        )
    except CoachLimitError as error:
        return jsonify(error=str(error)), 429
    except CoachError as error:
        return jsonify(error=str(error)), 400

    return jsonify(learner=message_json(learner_message), coach=message_json(coach_message))


@bp.route("/challenges/<slug>/review", methods=["POST"])
@api_role_required(RoleType.LEARNER)
@rate_limit("review")
def review(slug):
    """Review the learner's passing code (PR-C3)."""
    challenge = get_published(slug)
    if challenge is None:
        return _not_found()

    try:
        message = review_solution(current_user, challenge)
    except CoachError as error:
        return jsonify(error=str(error)), 400

    return jsonify(message_json(message))


def _rate(rate_function, item_id):
    """Shared handling for both rating endpoints."""
    payload = _json_payload()
    if payload is None:
        return jsonify(error="Send the rating as JSON."), 400

    try:
        item = rate_function(current_user, item_id, payload.get("rating"))
    except CoachNotFoundError as error:
        return jsonify(error=str(error)), 404
    except CoachError as error:
        return jsonify(error=str(error)), 400

    return jsonify(rating=item.rating)


@bp.route("/coach-messages/<int:message_id>/rating", methods=["POST"])
@api_role_required(RoleType.LEARNER)
def rate(message_id):
    """Thumbs up or down on one of the learner's Coach replies (PR-C6)."""
    return _rate(rate_message, message_id)


@bp.route("/hints/<int:hint_id>/rating", methods=["POST"])
@api_role_required(RoleType.LEARNER)
def rate_hint_route(hint_id):
    """Thumbs up or down on one of the learner's hints (PR-C6)."""
    return _rate(rate_hint, hint_id)