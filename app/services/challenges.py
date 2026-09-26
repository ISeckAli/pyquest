"""
Challenge service: creating and editing challenges, their test cases and
fallback hints, the publishing lifecycle, and the learner library
(spec FR04, FR12, PR-L1).

Lifecycle (SRS Part C, Figure 7):

    Draft --publish--> Published --unpublish--> Unpublished --publish--> ...
    Draft or Unpublished --delete--> removed (only if never attempted)

Publishing requires enough visible and hidden test cases and a reference
solution. The spec also requires the reference solution to pass every
test. Under decision DR-03 the server never runs code, so that check runs
in the instructor's browser; this service checks everything that can be
checked without running code.
"""

import re
import textwrap
from datetime import UTC, datetime

from flask import current_app
from sqlalchemy import delete, func, select

from app.extensions import db
from app.models import (
    Challenge,
    ChallengeStatus,
    Difficulty,
    FallbackHint,
    RoleType,
    SavedCode,
    Submission,
    TestCase,
    Topic,
)

TITLE_MIN_LENGTH = 3
TITLE_MAX_LENGTH = 120  # Matches the challenge.title column.
TOPIC_NAME_MIN_LENGTH = 2
TOPIC_NAME_MAX_LENGTH = 60  # Matches the topic.name column.
XP_MIN = 1
XP_MAX = 500

# Slugs are cut to this length before any "-2" style suffix is added, which
# keeps the result within the 140-character slug column.
SLUG_BASE_MAX_LENGTH = 120


class ChallengeError(Exception):
    """A challenge change was rejected. The message is safe to show.

    Attributes:
        field: the form field the message belongs to, if any.
        problems: for a refused publish, every requirement still unmet, so
            the instructor sees the full list at once instead of one at a time.
    """

    def __init__(self, message, field=None, problems=None):
        super().__init__(message)
        self.field = field
        self.problems = problems or []


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def slugify(text):
    """Turn a title into a URL-friendly slug: "Loops & Ranges" -> "loops-ranges"."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:SLUG_BASE_MAX_LENGTH].strip("-") or "item"


def _unique_slug(model, text):
    """Return a slug for text that no existing row of model already uses.

    A clash gets a numbered suffix: "reverse-a-string", "reverse-a-string-2".
    """
    base = slugify(text)
    slug = base
    suffix = 2
    while db.session.scalar(select(model.id).where(model.slug == slug)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def normalise_newlines(text):
    """Convert Windows (\\r\\n) and old Mac (\\r) line endings to \\n.

    Browsers send text typed into a multi-line box with \\r\\n line endings,
    but Python programs print \\n. Normalising when saving means expected
    outputs compare correctly against real program output later.
    """
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def clean_code(text):
    """Tidy pasted code: normal line endings, and no indentation shared by
    every line.

    Code copied from a web page or document often arrives with every line
    indented. Python rejects that ("unexpected indent"), so learners would
    start with broken starter code. textwrap.dedent removes only the
    indentation that all lines share, so relative indentation (such as the
    inside of a loop) is kept. Blank lines at the start and end are dropped.

    Used for starter code and reference solutions only, never for expected
    outputs, where leading spaces can be part of the correct answer.
    """
    return textwrap.dedent(normalise_newlines(text)).strip("\n")


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

def create_topic(name, description="", sort_order=0):
    """Create a topic. Names are unique regardless of capitals."""
    name = name.strip()
    if not TOPIC_NAME_MIN_LENGTH <= len(name) <= TOPIC_NAME_MAX_LENGTH:
        raise ChallengeError(
            f"Topic name must be {TOPIC_NAME_MIN_LENGTH} to "
            f"{TOPIC_NAME_MAX_LENGTH} characters long.",
            "name",
        )

    duplicate = db.session.scalar(
        select(Topic.id).where(func.lower(Topic.name) == name.lower())
    )
    if duplicate is not None:
        raise ChallengeError("A topic with this name already exists.", "name")

    topic = Topic(
        name=name,
        slug=_unique_slug(Topic, name),
        description=description.strip(),
        sort_order=sort_order,
    )
    db.session.add(topic)
    db.session.commit()
    return topic


def list_topics():
    """All topics in learning-path order."""
    return db.session.scalars(select(Topic).order_by(Topic.sort_order, Topic.name)).all()


# ---------------------------------------------------------------------------
# Creating and editing challenges
# ---------------------------------------------------------------------------

def _clean_details(title, description, topic, difficulty, xp_value):
    """Validate challenge details and return them cleaned.

    Raises:
        ChallengeError: naming the first field that is invalid.
    """
    title = (title or "").strip()
    if not TITLE_MIN_LENGTH <= len(title) <= TITLE_MAX_LENGTH:
        raise ChallengeError(
            f"Title must be {TITLE_MIN_LENGTH} to {TITLE_MAX_LENGTH} characters long.",
            "title",
        )

    description = normalise_newlines(description).strip()
    if not description:
        raise ChallengeError("Describe the problem the learner must solve.", "description")

    if not isinstance(topic, Topic):
        raise ChallengeError("Choose a topic.", "topic")

    try:
        difficulty = Difficulty(difficulty)
    except ValueError:
        raise ChallengeError("Choose a difficulty.", "difficulty") from None

    if xp_value is None:
        xp_value = current_app.config["CHALLENGE_XP_BY_DIFFICULTY"][difficulty.value]
    elif not (isinstance(xp_value, int) and XP_MIN <= xp_value <= XP_MAX):
        raise ChallengeError(f"XP must be a whole number from {XP_MIN} to {XP_MAX}.", "xp_value")

    return title, description, difficulty, xp_value


def create_challenge(
    author, title, description, topic, difficulty,
    starter_code="", reference_solution="", xp_value=None,
):
    """Create a challenge as a Draft and return it.

    Args:
        author: the instructor's UserAccount, or None for seeded content.
        xp_value: None uses the default for the difficulty (config).
    """
    title, description, difficulty, xp_value = _clean_details(
        title, description, topic, difficulty, xp_value
    )

    challenge = Challenge(
        title=title,
        slug=_unique_slug(Challenge, title),
        description=description,
        topic=topic,
        difficulty=difficulty,
        xp_value=xp_value,
        starter_code=clean_code(starter_code),
        reference_solution=clean_code(reference_solution),
        status=ChallengeStatus.DRAFT,
        author_id=author.party_id if author is not None else None,
    )
    db.session.add(challenge)
    db.session.commit()
    return challenge


def update_challenge(
    challenge, title, description, topic, difficulty,
    starter_code="", reference_solution="", xp_value=None,
):
    """Replace a challenge's details. The slug never changes.

    A published challenge must keep a reference solution, because the
    publish rule has to stay true for as long as learners can see it.
    """
    title, description, difficulty, xp_value = _clean_details(
        title, description, topic, difficulty, xp_value
    )
    reference_solution = clean_code(reference_solution)

    if challenge.is_published and not reference_solution.strip():
        raise ChallengeError(
            "A published challenge must keep a reference solution.", "reference_solution"
        )

    challenge.title = title
    challenge.description = description
    challenge.topic = topic
    challenge.difficulty = difficulty
    challenge.xp_value = xp_value
    challenge.starter_code = clean_code(starter_code)
    challenge.reference_solution = reference_solution
    db.session.commit()


# ---------------------------------------------------------------------------
# Test cases and fallback hints
# ---------------------------------------------------------------------------

def add_test_case(challenge, input_data, expected_output, is_hidden):
    """Add a test case to the end of a challenge's list and return it."""
    expected_output = normalise_newlines(expected_output)
    if not expected_output.strip():
        raise ChallengeError(
            "Enter the output the program should print.", "expected_output"
        )

    test_case = TestCase(
        input_data=normalise_newlines(input_data),
        expected_output=expected_output,
        is_hidden=bool(is_hidden),
        sort_order=len(challenge.test_cases),
    )
    challenge.test_cases.append(test_case)
    db.session.commit()
    return test_case


def remove_test_case(test_case):
    """Delete a test case, refusing if a published challenge would break
    the publish rule without it."""
    challenge = test_case.challenge
    remaining = [test for test in challenge.test_cases if test is not test_case]

    if challenge.is_published:
        problems = _test_count_problems(remaining)
        if problems:
            raise ChallengeError(
                "A published challenge must keep its minimum test cases. "
                "Unpublish it first, or add another test before removing this one.",
                problems=problems,
            )

    # Removing it from the list deletes it (delete-orphan cascade).
    challenge.test_cases.remove(test_case)
    for position, test in enumerate(challenge.test_cases):
        test.sort_order = position
    db.session.commit()


def set_fallback_hints(challenge, texts):
    """Replace a challenge's fallback hints with the non-blank texts given."""
    max_hints = current_app.config["CHALLENGE_MAX_FALLBACK_HINTS"]
    cleaned = [normalise_newlines(text).strip() for text in texts if text and text.strip()]

    if len(cleaned) > max_hints:
        raise ChallengeError(
            f"A challenge can have at most {max_hints} fallback hints.", "fallback_hints"
        )

    challenge.fallback_hints.clear()
    for position, text in enumerate(cleaned):
        challenge.fallback_hints.append(FallbackHint(text=text, sort_order=position))
    db.session.commit()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def _plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _test_count_problems(test_cases):
    """List the ways a set of test cases falls short of the publish rule."""
    min_visible = current_app.config["CHALLENGE_MIN_VISIBLE_TESTS"]
    min_hidden = current_app.config["CHALLENGE_MIN_HIDDEN_TESTS"]
    visible = sum(1 for test in test_cases if not test.is_hidden)
    hidden = len(test_cases) - visible

    problems = []
    if visible < min_visible:
        problems.append(
            f"Add at least {_plural(min_visible, 'visible test case')} (currently {visible})."
        )
    if hidden < min_hidden:
        problems.append(
            f"Add at least {_plural(min_hidden, 'hidden test case')} (currently {hidden})."
        )
    return problems


def publish_problems(challenge):
    """Every requirement a challenge still misses before it can be published."""
    problems = _test_count_problems(challenge.test_cases)
    if not challenge.reference_solution.strip():
        problems.append("Add a reference solution.")
    return problems


def publish(challenge, now=None):
    """Make a Draft or Unpublished challenge visible to learners.

    Raises:
        ChallengeError: if it is already published, or requirements are
            unmet (all of them listed in error.problems).
    """
    if challenge.is_published:
        raise ChallengeError("This challenge is already published.")

    problems = publish_problems(challenge)
    if problems:
        raise ChallengeError("This challenge is not ready to publish.", problems=problems)

    challenge.status = ChallengeStatus.PUBLISHED
    challenge.published_at = challenge.published_at or now or datetime.now(UTC)
    db.session.commit()


def unpublish(challenge):
    """Hide a published challenge from learners without deleting it."""
    if not challenge.is_published:
        raise ChallengeError("Only a published challenge can be unpublished.")

    challenge.status = ChallengeStatus.UNPUBLISHED
    db.session.commit()


def delete_challenge(challenge):
    """Delete a Draft or Unpublished challenge with its tests and hints.

    A published challenge must be unpublished first (state diagram), so a
    challenge learners can see never vanishes in a single step. A challenge
    that learners have attempted can never be deleted, only unpublished, so
    their submission history and the XP it records stay intact.
    """
    if challenge.is_published:
        raise ChallengeError("Unpublish this challenge before deleting it.")

    attempted = db.session.scalar(
        select(Submission.id).where(Submission.challenge_id == challenge.id).limit(1)
    )
    if attempted is not None:
        raise ChallengeError(
            "Learners have attempted this challenge, so it can be unpublished but "
            "not deleted. This keeps their submission history intact."
        )

    # Working copies saved while it was published have no value once the
    # challenge is gone.
    db.session.execute(delete(SavedCode).where(SavedCode.challenge_id == challenge.id))
    db.session.delete(challenge)
    db.session.commit()


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def can_manage(account, challenge):
    """True if the account may edit, publish, or delete this challenge.

    Instructors manage their own challenges; system administrators manage
    all of them (spec section 4.2, open question 3).
    """
    if account.has_role(RoleType.SYSTEM_ADMINISTRATOR):
        return True
    return account.has_role(RoleType.INSTRUCTOR) and challenge.author_id == account.party_id


def list_manageable(account):
    """Challenges this account may manage, most recently changed first."""
    statement = select(Challenge).order_by(Challenge.updated_at.desc())
    if not account.has_role(RoleType.SYSTEM_ADMINISTRATOR):
        statement = statement.where(Challenge.author_id == account.party_id)
    return db.session.scalars(statement).all()


# ---------------------------------------------------------------------------
# Learner library
# ---------------------------------------------------------------------------

def _parse_difficulty(value):
    """Return a Difficulty for a filter value, or None if it is not one.

    Filter values come from the page address, which anyone can edit, so an
    unknown value is ignored rather than causing an error page.
    """
    try:
        return Difficulty(value) if value else None
    except ValueError:
        return None


def _library_order(challenge):
    """Sort key: learning-path topic order, then easiest first, then title."""
    return (
        challenge.topic.sort_order,
        challenge.topic.name.lower(),
        challenge.difficulty.rank,
        challenge.title.lower(),
    )


def list_published(topic_slug=None, difficulty=None, search=None):
    """Published challenges for the library, filtered and in path order (FR04).

    Args:
        topic_slug: only this topic.
        difficulty: only this difficulty ("beginner", ...); unknown values
            are ignored.
        search: text the title must contain, ignoring capitals.
    """
    statement = (
        select(Challenge)
        .join(Challenge.topic)
        .where(Challenge.status == ChallengeStatus.PUBLISHED)
    )

    if topic_slug:
        statement = statement.where(Topic.slug == topic_slug)

    level = _parse_difficulty(difficulty)
    if level is not None:
        statement = statement.where(Challenge.difficulty == level)

    search = (search or "").strip()
    if search:
        # autoescape treats % and _ in the search text as ordinary
        # characters rather than database wildcards.
        statement = statement.where(
            func.lower(Challenge.title).contains(search.lower(), autoescape=True)
        )

    return sorted(db.session.scalars(statement).all(), key=_library_order)


def get_published(slug):
    """The published challenge with this slug, or None."""
    return db.session.scalars(
        select(Challenge).where(
            Challenge.slug == slug, Challenge.status == ChallengeStatus.PUBLISHED
        )
    ).first()