"""
Tests for grading and the challenge API (spec FR06, FR07).

The key guarantee checked throughout: a hidden test's expected output never
leaves the server, in any response, whether the submission passes or fails.
"""

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, Submission, SubmissionStatus, UserAccount
from app.services.challenges import add_test_case, create_challenge, create_topic, publish
from app.services.grading import GradingError, grade_submission, level_for_xp, normalise_output

# A hidden test's expected output. It must never appear in anything sent to
# the browser. Its input is the same text reversed, so a correct
# "reverse the string" solution produces it.
HIDDEN_ANSWER = "SECRET-EXPECTED-OUTPUT"


def make_account(email="learner@example.com", roles=(RoleType.LEARNER,), with_profile=True):
    """Create an account with a placeholder password hash (never logs in)."""
    person = Person(display_name=email.split("@")[0], email=email)
    for role in roles:
        person.add_role(role)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account])
    if with_profile:
        db.session.add(LearnerProfile(person=person))
    db.session.commit()
    return account


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


def count_rows(model):
    return db.session.scalar(select(func.count()).select_from(model))


@pytest.fixture
def challenge(app):
    """A published challenge with one visible and two hidden tests."""
    topic = create_topic("Strings", sort_order=1)
    challenge = create_challenge(
        None, "Reverse a String", "Print the input reversed.", topic, "beginner",
        reference_solution="print(input()[::-1])",
    )
    add_test_case(challenge, "abc", "cba", is_hidden=False)
    add_test_case(challenge, "hello", "olleh", is_hidden=True)
    add_test_case(challenge, HIDDEN_ANSWER[::-1], HIDDEN_ANSWER, is_hidden=True)
    publish(challenge)
    return challenge


@pytest.fixture
def learner(app):
    return make_account()


def correct_results(challenge):
    """What a correct solution prints for every test (print adds \\n)."""
    return [
        {"test_id": test.id, "output": test.expected_output + "\n"}
        for test in challenge.test_cases
    ]


def results_with_wrong_hidden(challenge):
    results = correct_results(challenge)
    results[-1]["output"] = "wrong\n"
    return results


def api_url(challenge, action):
    return f"/api/challenges/{challenge.slug}/{action}"


# ---------------------------------------------------------------------------
# Output comparison and levels
# ---------------------------------------------------------------------------

def test_comparison_ignores_trailing_whitespace_only():
    assert normalise_output("cba  \r\n\n") == "cba"
    assert normalise_output("c b a") != normalise_output("cba")
    assert normalise_output("CBA") != normalise_output("cba")


@pytest.mark.parametrize(
    "total_xp, level",
    [(0, 1), (99, 1), (100, 2), (299, 2), (300, 3), (600, 4)],
)
def test_level_thresholds_follow_the_spec(total_xp, level):
    assert level_for_xp(total_xp) == level


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def test_correct_submission_passes_and_awards_xp(learner, challenge):
    submission, feedback = grade_submission(learner, challenge, "code", correct_results(challenge))

    assert submission.status == SubmissionStatus.PASSED
    assert submission.xp_awarded == 10
    assert learner.party.learner_profile.total_xp == 10
    assert feedback["passed"] is True
    assert count_rows(Submission) == 1


def test_failed_hidden_test_reveals_only_that_it_failed(learner, challenge):
    submission, feedback = grade_submission(
        learner, challenge, "code", results_with_wrong_hidden(challenge)
    )

    hidden_feedback = [test for test in feedback["tests"] if test["hidden"]]
    assert submission.status == SubmissionStatus.FAILED
    assert submission.xp_awarded == 0
    assert all(set(test) == {"number", "hidden", "passed"} for test in hidden_feedback)
    assert HIDDEN_ANSWER not in str(feedback)


def test_xp_is_awarded_only_for_the_first_solve(learner, challenge):
    grade_submission(learner, challenge, "code", correct_results(challenge))
    second, feedback = grade_submission(learner, challenge, "code", correct_results(challenge))

    assert second.xp_awarded == 0
    assert feedback["total_xp"] == 10


def test_solving_after_failing_still_awards_xp(learner, challenge):
    grade_submission(learner, challenge, "code", results_with_wrong_hidden(challenge))
    solved, _ = grade_submission(learner, challenge, "code", correct_results(challenge))

    assert solved.xp_awarded == 10


def test_runtime_errors_are_recorded_by_type(learner, challenge):
    results = correct_results(challenge)
    results[0] = {
        "test_id": results[0]["test_id"],
        "output": "",
        "error": "NameError: name 'text' is not defined",
    }

    submission, feedback = grade_submission(learner, challenge, "code", results)

    assert submission.status == SubmissionStatus.FAILED
    assert submission.error_category == "NameError"
    assert "NameError" in feedback["tests"][0]["error"]


def test_results_must_cover_every_test_exactly_once(learner, challenge):
    results = correct_results(challenge)

    with pytest.raises(GradingError):
        grade_submission(learner, challenge, "code", results[:-1])
    with pytest.raises(GradingError):
        grade_submission(learner, challenge, "code", results + [results[0]])
    with pytest.raises(GradingError):
        grade_submission(
            learner, challenge, "code", results[:-1] + [{"test_id": 99999, "output": ""}]
        )
    assert count_rows(Submission) == 0


def test_reaching_a_threshold_levels_up(learner, challenge):
    challenge.xp_value = 100
    db.session.commit()

    grade_submission(learner, challenge, "code", correct_results(challenge))

    assert learner.party.learner_profile.level == 2


def test_missing_learner_profile_is_created(app, challenge):
    account = make_account(with_profile=False)

    grade_submission(account, challenge, "code", correct_results(challenge))

    assert account.party.learner_profile.total_xp == 10


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def test_api_requires_login(client, challenge):
    response = client.get(api_url(challenge, "tests"))

    assert response.status_code == 401
    assert response.is_json


def test_api_refuses_accounts_without_learner_role(client, challenge):
    sign_in(client, make_account("staff@example.com", roles=(RoleType.INSTRUCTOR,)))

    assert client.get(api_url(challenge, "tests")).status_code == 403


def test_runnable_tests_never_include_hidden_expected_outputs(client, learner, challenge):
    sign_in(client, learner)

    response = client.get(api_url(challenge, "tests"))
    tests = response.get_json()["tests"]

    assert [test["hidden"] for test in tests] == [False, True, True]
    assert "expected" in tests[0]
    assert all("expected" not in test for test in tests if test["hidden"])
    assert HIDDEN_ANSWER not in response.get_data(as_text=True)


def test_submitting_through_the_api(client, learner, challenge):
    sign_in(client, learner)

    response = client.post(
        api_url(challenge, "submissions"),
        json={"code": "print(input()[::-1])", "results": correct_results(challenge)},
    )

    assert response.status_code == 200
    assert response.get_json()["passed"] is True
    assert response.get_json()["xp_awarded"] == 10


def test_failed_api_submission_never_leaks_the_hidden_answer(client, learner, challenge):
    sign_in(client, learner)

    response = client.post(
        api_url(challenge, "submissions"),
        json={"code": "print('wrong')", "results": results_with_wrong_hidden(challenge)},
    )

    assert response.get_json()["passed"] is False
    assert HIDDEN_ANSWER not in response.get_data(as_text=True)


def test_malformed_submissions_are_rejected(client, learner, challenge):
    sign_in(client, learner)
    url = api_url(challenge, "submissions")

    not_json = client.post(url, data="not json", content_type="text/plain")
    no_results = client.post(url, json={"code": "print(1)"})

    assert not_json.status_code == 400
    assert no_results.status_code == 400
    assert count_rows(Submission) == 0


def test_unknown_challenge_is_not_found(client, learner, challenge):
    sign_in(client, learner)

    assert client.get("/api/challenges/no-such-challenge/tests").status_code == 404