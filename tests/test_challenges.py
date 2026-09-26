"""
Tests for the challenge models and service (spec FR04, FR12, PR-L1, and the
SRS Challenge state diagram).
"""

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    Challenge,
    ChallengeStatus,
    Person,
    RoleType,
    TestCase,
    UserAccount,
)
from app.services.challenges import (
    ChallengeError,
    add_test_case,
    can_manage,
    create_challenge,
    create_topic,
    delete_challenge,
    list_published,
    publish,
    publish_problems,
    remove_test_case,
    set_fallback_hints,
    unpublish,
    update_challenge,
)


def make_account(email, *roles):
    """Create an account with the given roles.

    These tests never log in, so a placeholder stands in for the password
    hash, which avoids the deliberately slow real hashing.
    """
    person = Person(display_name=email.split("@")[0], email=email)
    for role in roles:
        person.add_role(role)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account])
    db.session.commit()
    return account


def count_rows(model):
    return db.session.scalar(select(func.count()).select_from(model))


@pytest.fixture
def instructor(app):
    return make_account("teach@example.com", RoleType.INSTRUCTOR)


@pytest.fixture
def strings(app):
    return create_topic("Strings", sort_order=1)


def new_challenge(author, topic, title="Reverse a String", difficulty="beginner", **details):
    return create_challenge(author, title, "Print the input reversed.", topic, difficulty, **details)


def make_ready(challenge):
    """Give a challenge everything the publish rule requires."""
    add_test_case(challenge, "abc", "cba", is_hidden=False)
    add_test_case(challenge, "hello", "olleh", is_hidden=True)
    add_test_case(challenge, "a", "a", is_hidden=True)
    challenge.reference_solution = "print(input()[::-1])"
    db.session.commit()


# ---------------------------------------------------------------------------
# Topics and creation
# ---------------------------------------------------------------------------

def test_topic_gets_slug_and_unique_name(app):
    topic = create_topic("Loops & Ranges")

    assert topic.slug == "loops-ranges"
    with pytest.raises(ChallengeError) as error:
        create_topic("loops & ranges")
    assert error.value.field == "name"


def test_new_challenge_is_a_draft_with_default_xp(instructor, strings):
    challenge = new_challenge(instructor, strings)

    assert challenge.status == ChallengeStatus.DRAFT
    assert challenge.slug == "reverse-a-string"
    assert challenge.xp_value == 10
    assert challenge.author_id == instructor.party_id


def test_default_xp_follows_difficulty(instructor, strings):
    medium = new_challenge(instructor, strings, title="Medium One", difficulty="intermediate")
    hard = new_challenge(instructor, strings, title="Hard One", difficulty="advanced")

    assert medium.xp_value == 25
    assert hard.xp_value == 50


def test_duplicate_titles_get_unique_slugs(instructor, strings):
    new_challenge(instructor, strings)
    second = new_challenge(instructor, strings)

    assert second.slug == "reverse-a-string-2"


@pytest.mark.parametrize(
    "changes, field",
    [
        ({"title": "ab"}, "title"),
        ({"description": "   "}, "description"),
        ({"difficulty": "expert"}, "difficulty"),
        ({"xp_value": 0}, "xp_value"),
        ({"topic": None}, "topic"),
    ],
)
def test_invalid_details_are_rejected(instructor, strings, changes, field):
    details = {
        "title": "Valid Title",
        "description": "A valid description.",
        "topic": strings,
        "difficulty": "beginner",
    }
    details.update(changes)

    with pytest.raises(ChallengeError) as error:
        create_challenge(instructor, **details)

    assert error.value.field == field
    assert count_rows(Challenge) == 0


def test_update_changes_details_but_keeps_slug(instructor, strings):
    challenge = new_challenge(instructor, strings)

    update_challenge(challenge, "Reverse Words", "Reverse each word.", strings, "intermediate")

    assert challenge.title == "Reverse Words"
    assert challenge.slug == "reverse-a-string"
    assert challenge.xp_value == 25


# ---------------------------------------------------------------------------
# Test cases and hints
# ---------------------------------------------------------------------------

def test_test_cases_keep_order_and_split_visible_hidden(instructor, strings):
    challenge = new_challenge(instructor, strings)
    make_ready(challenge)

    assert [test.input_data for test in challenge.test_cases] == ["abc", "hello", "a"]
    assert len(challenge.visible_tests) == 1
    assert len(challenge.hidden_tests) == 2


def test_test_case_text_uses_unix_line_endings(instructor, strings):
    challenge = new_challenge(instructor, strings)

    test = add_test_case(challenge, "a\r\nb", "x\r\ny", is_hidden=False)

    assert test.input_data == "a\nb"
    assert test.expected_output == "x\ny"


def test_test_case_requires_expected_output(instructor, strings):
    challenge = new_challenge(instructor, strings)

    with pytest.raises(ChallengeError) as error:
        add_test_case(challenge, "abc", "   ", is_hidden=False)

    assert error.value.field == "expected_output"


def test_fallback_hints_are_replaced_and_limited(instructor, strings):
    challenge = new_challenge(instructor, strings)

    set_fallback_hints(challenge, ["Think about slicing.", "   ", "Try a step of -1."])
    assert [hint.text for hint in challenge.fallback_hints] == [
        "Think about slicing.",
        "Try a step of -1.",
    ]

    with pytest.raises(ChallengeError) as error:
        set_fallback_hints(challenge, ["one", "two", "three", "four"])
    assert error.value.field == "fallback_hints"
    assert len(challenge.fallback_hints) == 2


# ---------------------------------------------------------------------------
# Lifecycle (SRS Figure 7)
# ---------------------------------------------------------------------------

def test_new_challenge_lists_every_publish_problem(instructor, strings):
    challenge = new_challenge(instructor, strings)

    assert len(publish_problems(challenge)) == 3
    with pytest.raises(ChallengeError) as error:
        publish(challenge)
    assert len(error.value.problems) == 3
    assert challenge.status == ChallengeStatus.DRAFT


def test_ready_challenge_publishes(instructor, strings):
    challenge = new_challenge(instructor, strings)
    make_ready(challenge)

    publish(challenge)

    assert challenge.status == ChallengeStatus.PUBLISHED
    assert challenge.published_at is not None


def test_republishing_keeps_the_original_publish_date(instructor, strings):
    challenge = new_challenge(instructor, strings)
    make_ready(challenge)
    publish(challenge)
    first_published = challenge.published_at

    unpublish(challenge)
    assert challenge.status == ChallengeStatus.UNPUBLISHED
    publish(challenge)

    assert challenge.published_at == first_published


def test_published_challenge_must_be_unpublished_before_deleting(instructor, strings):
    challenge = new_challenge(instructor, strings)
    make_ready(challenge)
    publish(challenge)

    with pytest.raises(ChallengeError):
        delete_challenge(challenge)

    unpublish(challenge)
    delete_challenge(challenge)

    assert count_rows(Challenge) == 0
    assert count_rows(TestCase) == 0


def test_published_challenge_cannot_drop_below_minimum_tests(instructor, strings):
    challenge = new_challenge(instructor, strings)
    make_ready(challenge)
    publish(challenge)

    with pytest.raises(ChallengeError):
        remove_test_case(challenge.hidden_tests[0])

    assert len(challenge.test_cases) == 3


# ---------------------------------------------------------------------------
# Library (FR04, PR-L1)
# ---------------------------------------------------------------------------

def test_library_lists_only_published_with_filters(instructor, strings):
    loops = create_topic("Loops", sort_order=2)
    reverse = new_challenge(instructor, strings)
    make_ready(reverse)
    publish(reverse)
    count_up = new_challenge(instructor, loops, title="Count Up", difficulty="intermediate")
    make_ready(count_up)
    publish(count_up)
    new_challenge(instructor, strings, title="Unfinished Draft")

    assert {c.title for c in list_published()} == {"Reverse a String", "Count Up"}
    assert [c.title for c in list_published(topic_slug="loops")] == ["Count Up"]
    assert [c.title for c in list_published(difficulty="beginner")] == ["Reverse a String"]
    assert [c.title for c in list_published(search="REVERSE")] == ["Reverse a String"]
    assert len(list_published(difficulty="not-a-level")) == 2


def test_library_orders_by_topic_then_difficulty(instructor, strings):
    loops = create_topic("Loops", sort_order=2)
    for topic, title, difficulty in [
        (loops, "Loop Basics", "beginner"),
        (strings, "String Puzzle", "advanced"),
        (strings, "String Basics", "beginner"),
    ]:
        challenge = new_challenge(instructor, topic, title=title, difficulty=difficulty)
        make_ready(challenge)
        publish(challenge)

    assert [c.title for c in list_published()] == [
        "String Basics",
        "String Puzzle",
        "Loop Basics",
    ]


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def test_only_the_author_or_an_administrator_can_manage(instructor, strings):
    other_instructor = make_account("other@example.com", RoleType.INSTRUCTOR)
    admin = make_account("admin@example.com", RoleType.SYSTEM_ADMINISTRATOR)
    learner = make_account("learner@example.com", RoleType.LEARNER)
    challenge = new_challenge(instructor, strings)

    assert can_manage(instructor, challenge)
    assert can_manage(admin, challenge)
    assert not can_manage(other_instructor, challenge)
    assert not can_manage(learner, challenge)