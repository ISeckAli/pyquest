"""
Grading service: turns a learner's test results into a pass or fail, records
the submission, and awards XP (spec FR06, FR07).

How grading works with code that runs in the browser (decision DR-03):

1. The browser asks for the challenge's runnable tests. It receives every
   test's input, but the expected output only for visible tests.
2. It runs the learner's code on each input and sends the outputs here.
3. This service compares them with the expected outputs, which for hidden
   tests never leave the server, and decides the result and XP.

Faking a pass would mean sending the correct output for each hidden input
without knowing the expected outputs, which in practice means solving the
problem. The server never runs learner code.
"""

import re

from sqlalchemy import select

from app.extensions import db
from app.models import LearnerProfile, Submission, SubmissionStatus
from app.services.challenges import normalise_newlines

MAX_CODE_LENGTH = 20_000
MAX_OUTPUT_LENGTH = 65_536  # 64 KB of output per test (spec FR06).
MAX_ERROR_LENGTH = 200
MAX_EXECUTION_MS = 60_000

# XP needed to move from level n to level n + 1 is LEVEL_XP_STEP * n (spec
# FR07, tunable): level 2 at 100 XP, level 3 at 300, level 4 at 600. Moves
# into config.py with the rest of gamification in Part 9.
LEVEL_XP_STEP = 100

# The error type at the start of a Python error message, such as the
# "NameError" in "NameError: name 'x' is not defined".
_ERROR_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,39}")


class GradingError(Exception):
    """The submission was malformed. The message is safe to show."""


# ---------------------------------------------------------------------------
# Comparing outputs and computing levels
# ---------------------------------------------------------------------------

def normalise_output(text):
    """Prepare program output for comparison.

    Ignores what learners cannot see and should not be failed for: line
    ending style, spaces at the ends of lines, and blank lines at the end
    (print() always adds a final newline). Everything else must match
    exactly, including capitals and spaces between words.
    """
    lines = normalise_newlines(text).split("\n")
    return "\n".join(line.rstrip() for line in lines).rstrip("\n")


def level_for_xp(total_xp):
    """The level reached with this much XP (level 1 at 0 XP)."""
    level = 1
    while total_xp >= LEVEL_XP_STEP * level * (level + 1) // 2:
        level += 1
    return level


def _error_category(error):
    """Reduce an error message to its type, such as "NameError"."""
    match = _ERROR_NAME.match(error.strip())
    return match.group(0) if match else "Error"


# ---------------------------------------------------------------------------
# What the browser receives
# ---------------------------------------------------------------------------

def runnable_tests(challenge):
    """The tests the browser needs in order to run the learner's code.

    Every test's input is included so it can be run. Expected outputs are
    included for visible tests only; hidden expected outputs stay here.
    """
    tests = []
    for test in challenge.test_cases:
        entry = {"id": test.id, "input": test.input_data, "hidden": test.is_hidden}
        if not test.is_hidden:
            entry["expected"] = test.expected_output
        tests.append(entry)
    return {"tests": tests}


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def grade_submission(account, challenge, code, results, execution_ms=None):
    """Grade results reported by the browser and record the submission.

    Args:
        account: the learner's UserAccount.
        challenge: the published Challenge.
        code: the learner's code as submitted.
        results: a list with one entry per test:
            {"test_id": int, "output": str, "error": str or None}.
        execution_ms: total run time reported by the browser, optional.

    Returns:
        (submission, feedback): the saved Submission, and a dictionary safe
        to send to the browser. Feedback on hidden tests says only whether
        each passed.

    Raises:
        GradingError: if the submission is malformed or does not match the
            challenge's tests.
    """
    code = _validate_code(code)
    outcomes = _validate_results(challenge, results)
    execution_ms = _validate_execution_ms(execution_ms)

    feedback_tests = []
    passed_count = 0
    first_error = None

    for number, test in enumerate(challenge.test_cases, start=1):
        output, error = outcomes[test.id]
        passed = error is None and normalise_output(output) == normalise_output(
            test.expected_output
        )
        if passed:
            passed_count += 1
        elif error is not None and first_error is None:
            first_error = _error_category(error)

        entry = {"number": number, "hidden": test.is_hidden, "passed": passed}
        if not test.is_hidden:
            # Visible tests are already shown as examples, so full details
            # help the learner see exactly what went wrong.
            entry.update(input=test.input_data, expected=test.expected_output, actual=output)
            if error is not None:
                entry["error"] = error
        feedback_tests.append(entry)

    total_count = len(challenge.test_cases)
    passed_all = passed_count == total_count
    profile = _learner_profile(account)

    # XP only for the first passing submission (spec FR07), so repeating
    # a solved challenge cannot farm XP. Checked before this submission is
    # added, so it only looks at earlier attempts.
    xp_awarded = 0
    if passed_all and not _already_solved(account.party_id, challenge.id):
        xp_awarded = challenge.xp_value
        profile.total_xp += xp_awarded
        profile.level = level_for_xp(profile.total_xp)

    submission = Submission(
        party_id=account.party_id,
        challenge_id=challenge.id,
        code=code,
        status=SubmissionStatus.PASSED if passed_all else SubmissionStatus.FAILED,
        passed_count=passed_count,
        total_count=total_count,
        error_category=first_error,
        execution_ms=execution_ms,
        xp_awarded=xp_awarded,
    )
    db.session.add(submission)

    # One commit for the submission and the XP together, so they can never
    # disagree (spec FR07).
    db.session.commit()

    feedback = {
        "passed": passed_all,
        "passed_count": passed_count,
        "total_count": total_count,
        "xp_awarded": xp_awarded,
        "total_xp": profile.total_xp,
        "level": profile.level,
        "tests": feedback_tests,
    }
    return submission, feedback


def _already_solved(party_id, challenge_id):
    return (
        db.session.scalar(
            select(Submission.id).where(
                Submission.party_id == party_id,
                Submission.challenge_id == challenge_id,
                Submission.status == SubmissionStatus.PASSED,
            )
        )
        is not None
    )


def _learner_profile(account):
    """The learner's profile, created if missing.

    Sign-up always creates one, but a learner role granted later from the
    command line does not, so this makes sure one exists.
    """
    person = account.party
    if person.learner_profile is None:
        person.learner_profile = LearnerProfile(
            total_xp=0, level=1, current_streak=0, longest_streak=0
        )
        db.session.add(person.learner_profile)
    return person.learner_profile


# ---------------------------------------------------------------------------
# Validating what the browser sent
# ---------------------------------------------------------------------------

def _validate_code(code):
    if not isinstance(code, str) or len(code) > MAX_CODE_LENGTH:
        raise GradingError(f"Code is missing or longer than {MAX_CODE_LENGTH} characters.")
    return normalise_newlines(code)


def _validate_results(challenge, results):
    """Check there is exactly one result for each of the challenge's tests.

    Returns a dictionary of test id -> (output, error or None).
    """
    mismatch = "The results do not match this challenge's tests. Reload the page and try again."
    if not isinstance(results, list):
        raise GradingError(mismatch)

    expected_ids = {test.id for test in challenge.test_cases}
    outcomes = {}

    for item in results:
        if not isinstance(item, dict):
            raise GradingError(mismatch)

        test_id = item.get("test_id")
        # type() rather than isinstance(), because True and False count as
        # integers in Python and must not pass as test ids.
        if type(test_id) is not int or test_id not in expected_ids or test_id in outcomes:
            raise GradingError(mismatch)

        output = item.get("output", "")
        if not isinstance(output, str) or len(output) > MAX_OUTPUT_LENGTH:
            raise GradingError("A test produced no output record or too much output.")

        error = item.get("error")
        if error is not None and not isinstance(error, str):
            raise GradingError(mismatch)
        error = error.strip()[:MAX_ERROR_LENGTH] if error else None

        outcomes[test_id] = (output, error)

    if set(outcomes) != expected_ids:
        raise GradingError(mismatch)
    return outcomes


def _validate_execution_ms(execution_ms):
    if execution_ms is None:
        return None
    if type(execution_ms) is not int or not 0 <= execution_ms <= MAX_EXECUTION_MS:
        raise GradingError("Execution time is not valid.")
    return execution_ms