"""
Views for the challenge library and individual challenge pages.
"""

from itertools import groupby
from operator import attrgetter

from flask import abort, render_template, request, url_for
from flask_login import current_user

from app.challenges import bp
from app.models import Difficulty, RoleType
from app.services.challenges import get_published, list_published, list_topics

# The Monaco editor is loaded from a free public CDN, pinned to an exact
# version so every learner gets the same editor (spec DR-11: $0 hosting).
MONACO_BASE = "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2"


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
    signed-in learners the code workspace (FR05).

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
        editor_config = {
            "starterCode": challenge.starter_code,
            "testsUrl": url_for("api.challenge_tests", slug=challenge.slug),
            "submitUrl": url_for("api.submit", slug=challenge.slug),
            "workerUrl": url_for("static", filename="js/python-worker.js"),
            "monacoBase": MONACO_BASE,
        }

    return render_template(
        "challenges/detail.html",
        challenge=challenge,
        preview=False,
        can_solve=can_solve,
        editor_config=editor_config,
        monaco_loader=f"{MONACO_BASE}/min/vs/loader.js",
    )