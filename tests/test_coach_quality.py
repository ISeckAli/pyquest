"""
Tests for the Coach quality check set (spec PR-C7), using the fake AI
provider. The real check runs with: flask --app app coach-check
"""

from app.services.ai_service import get_provider
from app.services.coach_quality import CASES, HIDDEN_OUTPUT, REFERENCE_SOLUTION


def run_check(app):
    return app.test_cli_runner().invoke(args=["coach-check"])


def test_the_set_has_twenty_attempts_including_tricks(app):
    assert len(CASES) >= 20
    assert sum(name.startswith("trick") for name, _ in CASES) >= 8


def test_safe_replies_pass_the_check(app):
    result = run_check(app)

    assert result.exit_code == 0
    assert "Coach quality check passed" in result.output


def test_a_reply_with_a_code_block_blocks_the_release(app):
    get_provider().replies = ["Here you go:\n```python\nprint(input().upper() + '!')\n```"]

    result = run_check(app)

    assert result.exit_code != 0
    assert "LEAK" in result.output
    assert "Do not release" in result.output


def test_a_reply_revealing_a_hidden_answer_blocks_the_release(app):
    get_provider().replies = [f"The hidden test expects {HIDDEN_OUTPUT}"]

    result = run_check(app)

    assert result.exit_code != 0
    assert "LEAK" in result.output


def test_an_unavailable_ai_cannot_pass_the_check(app):
    get_provider().fail = True

    result = run_check(app)

    assert result.exit_code != 0
    assert "could not be completed" in result.output


def test_the_check_never_sends_hidden_answers_or_the_solution(app):
    """The Coach never supplies the reference solution or a hidden answer.

    The "correct solution" attempt is a learner who has already written the
    reference solution, so that text appears in its prompt as the learner's
    own code. The rule is that the Coach never adds it: it must not appear
    in any prompt whose learner code is something else.
    """
    run_check(app)
    prompts = [call["prompt"] for call in get_provider().calls]

    assert len(prompts) == len(CASES)
    assert all(HIDDEN_OUTPUT not in prompt for prompt in prompts)
    for (name, code), prompt in zip(CASES, prompts):
        if code != REFERENCE_SOLUTION:
            assert REFERENCE_SOLUTION not in prompt, name