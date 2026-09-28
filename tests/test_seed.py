"""
Tests for the seed content (spec Part 12).

The most important test runs every reference solution against its own
tests in a separate Python process, so a challenge with a wrong expected
output can never be committed. This is the server-side equivalent of the
instructor's "Check reference solution" button, run automatically in CI.
"""

import subprocess
import sys

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import Challenge, ChallengeStatus, Topic
from app.seed_data import SEED_CHALLENGES
from app.services.challenges import create_topic
from app.services.grading import normalise_output
from app.services.seed import seed_content


def count(model):
    return db.session.scalar(select(func.count()).select_from(model))


def test_seeding_creates_published_challenges_with_tests_and_hints(app):
    created = seed_content()

    assert len(created) == len(SEED_CHALLENGES)
    assert count(Topic) == 3
    for challenge in created:
        assert challenge.status == ChallengeStatus.PUBLISHED
        assert len(challenge.visible_tests) >= 1
        assert len(challenge.test_cases) - len(challenge.visible_tests) >= 2
        assert len(challenge.fallback_hints) >= 2


def test_seeding_twice_adds_nothing(app):
    seed_content()

    assert seed_content() == []
    assert count(Challenge) == len(SEED_CHALLENGES)


def test_an_existing_topic_is_reused(app):
    create_topic("Strings", "My own description.", 1)

    seed_content()

    assert count(Topic) == 3


@pytest.mark.parametrize("spec", SEED_CHALLENGES, ids=lambda spec: spec["title"])
def test_reference_solution_passes_every_test(spec):
    """Runs our own trusted seed code in a separate Python process."""
    for input_data, expected, _ in spec["tests"]:
        result = subprocess.run(
            [sys.executable, "-c", spec["reference"]],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert normalise_output(result.stdout) == normalise_output(expected), (
            f"{spec['title']}: input {input_data!r}"
        )