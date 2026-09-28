"""
Loads the starter content in app/seed_data.py (spec Part 12).

Safe to run any number of times: existing topics are reused (matched by
slug) and challenges that already exist are skipped, so running it again
after adding new challenges to seed_data.py adds only the new ones.
"""

from sqlalchemy import select

from app.extensions import db
from app.models import Challenge, Topic
from app.seed_data import SEED_CHALLENGES, SEED_TOPICS
from app.services.challenges import (
    add_test_case,
    create_challenge,
    create_topic,
    publish,
    set_fallback_hints,
    slugify,
)


def seed_content():
    """Create any missing seed topics and challenges, published.

    Returns:
        The challenges created by this run (empty if all already existed).
    """
    topics = {}
    for spec in SEED_TOPICS:
        topic = db.session.scalars(select(Topic).where(Topic.slug == spec["slug"])).first()
        if topic is None:
            topic = create_topic(spec["name"], spec["description"], spec["order"])
        topics[spec["slug"]] = topic

    created = []
    for spec in SEED_CHALLENGES:
        exists = db.session.scalar(
            select(Challenge.id).where(Challenge.slug == slugify(spec["title"]))
        )
        if exists is not None:
            continue

        challenge = create_challenge(
            None,
            spec["title"],
            spec["description"],
            topics[spec["topic"]],
            spec["difficulty"],
            starter_code=spec["starter"],
            reference_solution=spec["reference"],
        )
        for input_data, expected_output, is_hidden in spec["tests"]:
            add_test_case(challenge, input_data, expected_output, is_hidden)
        set_fallback_hints(challenge, spec["hints"])
        publish(challenge)
        created.append(challenge)

    return created