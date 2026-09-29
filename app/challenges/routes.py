"""
Views for the challenge library and individual challenge pages.
"""

from itertools import groupby
from operator import attrgetter

from flask import abort, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select

from app.challenges import bp
from app.extensions import db
from app.models import CoachMessage, CoachMessageKind, Difficulty, RoleType
from app.services.challenges import get_published, list_published, list_topics
from app.services.coach import MAX_HINTS_PER_CHALLENGE, hints_used
from app.services.coach_chat import CHAT_DAILY_LIMIT, MAX_MESSAGE_LENGTH, conversation
from app.services.guest import GUEST_CHAT_LIMIT, is_guest
from app.services.workspace import get_saved_code

# The Monaco editor is loaded from a free public CDN, pinned to an exact
# version so every learner gets the same editor (spec DR-11: $0 hosting).
MONACO_BASE = "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2"


def _message_json(message):
    """A Coach message as the page scripts need it."""
    return {
        "id": message.id,
        "sender": message.sender.value,
        "text": message.content,
        "source": message.source.value,
        "rating": message.rating,
    }


def _url_template(endpoint, **values):
    """A URL with a {id} placeholder the page fills in, such as
    /api/coach-messages/{id}/rating."""
    return url_for(endpoint, **values).replace("/0/", "/{id}/")


@bp.route("/challenges")
def library():
    """The challenge library, grouped by topic in learning-path order (FR04).

    Filters are read from the page address (for example
    /challenges?difficulty=beginner), so a filtered view can be bookmarked
    or shared. Unknown filter values are ignored by the service rather than
    causing an error page.
    """
    filters = {
        "q": request.args.get("q", "").strip(),
        "topic": request.args.get("topic", "").strip(),
        "difficulty": request.args.get("difficulty", "").strip(),
    }

    challenges = list_published(
        topic_slug=filters["topic"] or None,
        difficulty=filters["difficulty"] or None,
        search=filters["q"],
    )

    # The service already sorts by topic, so groupby can collect each
    # topic's challenges in a single pass without reordering the topics.
    groups = [
        (topic, list(topic_challenges))
        for topic, topic_challenges in groupby(challenges, key=attrgetter("topic"))
    ]

    return render_template(
        "challenges/library.html",
        groups=groups,
        topics=list_topics(),
        difficulties=list(Difficulty),
        filters=filters,
    )


@bp.route("/challenges/<slug>")
def detail(slug):
    """A published challenge: the problem, its visible examples, and for
    signed-in learners the code workspace (FR05) and the AI Coach (5.9).

    Drafts and unpublished challenges return 404 Not Found, so their
    addresses reveal nothing. Hidden tests and the reference solution are
    never passed to the template, so they cannot appear in the page; the
    workspace fetches runnable tests from the API instead.
    """
    challenge = get_published(slug)
    if challenge is None:
        abort(404)

    can_solve = current_user.is_authenticated and current_user.has_role(RoleType.LEARNER)

    editor_config = None
    if can_solve:
        saved = get_saved_code(current_user, challenge)
        review = db.session.scalars(
            select(CoachMessage).where(
                CoachMessage.party_id == current_user.party_id,
                CoachMessage.challenge_id == challenge.id,
                CoachMessage.kind == CoachMessageKind.REVIEW,
            )
        ).first()
        guest = is_guest(current_user)

        editor_config = {
            # The editor opens with the learner's saved work when there is
            # any; "Reset code" goes back to the starter code.
            "initialCode": saved if saved is not None else challenge.starter_code,
            "starterCode": challenge.starter_code,
            "testsUrl": url_for("api.challenge_tests", slug=challenge.slug),
            "submitUrl": url_for("api.submit", slug=challenge.slug),
            "saveUrl": url_for("api.save_workspace_code", slug=challenge.slug),
            "workerUrl": url_for("static", filename="js/python-worker.js"),
            "monacoBase": MONACO_BASE,
            # AI Coach: hints (PR-C1) and failure explanations (PR-C2).
            "hintsUrl": url_for("api.request_hint", slug=challenge.slug),
            "explanationUrlTemplate": _url_template("api.explain_submission", submission_id=0),
            "maxHints": MAX_HINTS_PER_CHALLENGE,
            "hints": [
                {
                    "id": hint.id,
                    "level": hint.level,
                    "text": hint.text,
                    "source": hint.source.value,
                    "rating": hint.rating,
                }
                for hint in hints_used(current_user, challenge)
            ],
            # AI Coach: chat (PR-C4), review (PR-C3), and ratings (PR-C6).
            # Earlier messages and any review come back with the page, so
            # nothing is lost when the learner leaves and returns.
            "chatUrl": url_for("api.chat", slug=challenge.slug),
            "reviewUrl": url_for("api.review", slug=challenge.slug),
            "ratingUrlTemplate": _url_template("api.rate", message_id=0),
            "hintRatingUrlTemplate": _url_template("api.rate_hint_route", hint_id=0),
            # Guests have a small total allowance rather than a daily one
            # (spec PR-A3), so the page states whichever applies.
            "chatLimit": GUEST_CHAT_LIMIT if guest else CHAT_DAILY_LIMIT,
            "chatLimitIsGuest": guest,
            "maxMessageLength": MAX_MESSAGE_LENGTH,
            "chat": [_message_json(message) for message in conversation(current_user, challenge)],
            "review": _message_json(review) if review is not None else None,
        }

    return render_template(
        "challenges/detail.html",
        challenge=challenge,
        preview=False,
        can_solve=can_solve,
        editor_config=editor_config,
        monaco_loader=f"{MONACO_BASE}/min/vs/loader.js",
    )