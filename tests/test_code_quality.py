"""
Tests for code quality scoring (Part 14): each style check, the score, the
seed solutions, grading feedback, and the Coach review.
"""

import pytest

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, UserAccount
from app.seed_data import SEED_CHALLENGES
from app.services.ai_service import get_provider
from app.services.challenges import add_test_case, create_challenge, create_topic, publish
from app.services.code_quality import analyze


def failed_titles(code):
    return [check["title"] for check in analyze(code)["checks"] if not check["passed"]]


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def test_clean_code_scores_full_marks():
    report = analyze("word = input()\nprint(word.upper())")

    assert report["score"] == 100
    assert report["rating"] == "Excellent"


def test_short_names_are_flagged_but_loop_and_maths_names_are_not():
    assert "Descriptive names" in failed_titles("a = int(input())\nprint(a)")
    assert failed_titles("x = int(input())\nfor i in range(x):\n    print(i)") == []


def test_camel_case_is_flagged_but_constants_are_not():
    assert "snake_case names" in failed_titles("wordCount = 3\nprint(wordCount)")
    assert failed_titles("LIMIT = 3\nprint(LIMIT)") == []


def test_reusing_a_built_in_name_is_flagged():
    assert "No built-in names reused" in failed_titles("list = [1, 2]\nprint(list)")


def test_unused_variables_are_flagged_but_loop_variables_are_not():
    assert "No unused variables" in failed_titles("total = 0\nprint(5)")
    assert failed_titles("for attempt in range(3):\n    print('hi')") == []


def test_deep_nesting_is_flagged_but_elif_chains_are_not():
    deep = "for a1 in range(2):\n    if a1:\n        while a1:\n            if a1:\n                print(a1)\n            break"
    ladder = "score = int(input())\nif score >= 90:\n    print('A')\nelif score >= 80:\n    print('B')\nelif score >= 70:\n    print('C')\nelif score >= 60:\n    print('D')\nelse:\n    print('F')"

    assert "Shallow nesting" in failed_titles(deep)
    assert "Shallow nesting" not in failed_titles(ladder)


def test_long_lines_are_flagged():
    assert "Short lines" in failed_titles("print('" + "a" * 90 + "')")


def test_comparisons_with_true_or_none_and_bare_excepts_are_flagged():
    code = "done = True\nif done == True:\n    print(1)\ntry:\n    print(int('x'))\nexcept:\n    print(2)"

    titles = failed_titles(code)

    assert "Clear comparisons" in titles
    assert "Specific exceptions" in titles


def test_unparseable_code_has_no_report():
    assert analyze("print(") is None


@pytest.mark.parametrize("spec", SEED_CHALLENGES, ids=lambda spec: spec["title"])
def test_every_seed_solution_can_be_scored(spec):
    report = analyze(spec["reference"])

    assert report is not None
    assert report["score"] >= 50


# ---------------------------------------------------------------------------
# Grading feedback and the Coach review
# ---------------------------------------------------------------------------

@pytest.fixture
def learner(client):
    person = Person(display_name="Ada", email="ada@example.com")
    person.add_role(RoleType.LEARNER)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account, LearnerProfile(person=person)])
    db.session.commit()
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True
    return account


@pytest.fixture
def challenge(app):
    topic = create_topic("Strings", sort_order=1)
    challenge = create_challenge(
        None, "Shout", "Shout the input.", topic, "beginner",
        reference_solution="print(input().upper())",
    )
    add_test_case(challenge, "hi", "HI", is_hidden=False)
    add_test_case(challenge, "a", "A", is_hidden=True)
    add_test_case(challenge, "b", "B", is_hidden=True)
    publish(challenge)
    return challenge


def submit(client, challenge, code, correct=True):
    results = [
        {"test_id": test.id, "output": test.expected_output if correct else "wrong"}
        for test in challenge.test_cases
    ]
    return client.post(
        f"/api/challenges/{challenge.slug}/submissions", json={"code": code, "results": results}
    ).get_json()


def test_passing_feedback_includes_a_quality_report(client, learner, challenge):
    feedback = submit(client, challenge, "a = input()\nprint(a.upper())")

    assert feedback["quality"]["score"] < 100
    assert "Descriptive names" in [c["title"] for c in feedback["quality"]["checks"] if not c["passed"]]


def test_failing_feedback_has_no_quality_report(client, learner, challenge):
    assert submit(client, challenge, "print('x')", correct=False)["quality"] is None


def test_the_coach_review_is_told_the_style_findings(client, learner, challenge):
    submit(client, challenge, "list = input()\nprint(list.upper())")

    client.post(f"/api/challenges/{challenge.slug}/review")

    assert "No built-in names reused" in get_provider().calls[-1]["prompt"]