"""
Workspace service: each learner's saved working copy of their code for a
challenge (spec FR05).
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import SavedCode
from app.services.challenges import normalise_newlines
from app.services.grading import MAX_CODE_LENGTH


class WorkspaceError(Exception):
    """Code could not be saved. The message is safe to show."""


def _find(account, challenge):
    return db.session.scalars(
        select(SavedCode).where(
            SavedCode.party_id == account.party_id,
            SavedCode.challenge_id == challenge.id,
        )
    ).first()


def get_saved_code(account, challenge):
    """The learner's saved code for this challenge, or None if nothing is saved."""
    saved = _find(account, challenge)
    return saved.code if saved is not None else None


def save_code(account, challenge, code):
    """Save the learner's working copy, replacing any earlier one."""
    if not isinstance(code, str) or len(code) > MAX_CODE_LENGTH:
        raise WorkspaceError(f"Code is missing or longer than {MAX_CODE_LENGTH} characters.")
    code = normalise_newlines(code)

    saved = _find(account, challenge)
    if saved is not None:
        saved.code = code
        db.session.commit()
        return

    db.session.add(SavedCode(party_id=account.party_id, challenge_id=challenge.id, code=code))
    try:
        db.session.commit()
    except IntegrityError:
        # Two saves arriving at the same moment (for example from two open
        # tabs) can both find nothing and both try to insert; the unique
        # rule stops the second, which then updates the row instead.
        db.session.rollback()
        _find(account, challenge).code = code
        db.session.commit()