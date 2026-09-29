"""
Ratings on hints (spec PR-C6). Ratings on other Coach replies live with
them in coach_chat.py; hints are stored in their own table, so they have
their own function here.
"""

from app.extensions import db
from app.models import Hint
from app.services.coach import CoachError
from app.services.coach_chat import RATINGS, CoachNotFoundError


def rate_hint(account, hint_id, rating):
    """Record the learner's thumbs up or down on one of their hints.

    Raises:
        CoachNotFoundError: if the hint does not exist or is not this learner's.
        CoachError: if the rating is not "up" or "down".
    """
    hint = db.session.get(Hint, hint_id)
    if hint is None or hint.party_id != account.party_id:
        raise CoachNotFoundError("Hint not found.")
    if rating not in RATINGS:
        raise CoachError('Rating must be "up" or "down".')

    hint.rating = rating
    db.session.commit()
    return hint