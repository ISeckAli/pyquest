"""
Views for the challenge library and individual challenge pages.
"""

from itertools import groupby
from operator import attrgetter

from flask import abort, render_template, request

from app.challenges import bp
from app.models import Difficulty
from app.services.challenges import get_published, list_published, list_topics


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
    """A published challenge: the problem and its visible examples.

    Drafts and unpublished challenges return 404 Not Found, so their
    addresses reveal nothing. Hidden tests and the reference solution are
    never passed to the template, so they cannot appear in the page.
    """
    challenge = get_published(slug)
    if challenge is None:
        abort(404)
    return render_template("challenges/detail.html", challenge=challenge, preview=False)