"""
Tests for the command-line tools in app/cli.py.

app.test_cli_runner() runs a command exactly as `flask --app app ...` would,
but inside the test's app, against the test's in-memory database.
"""

from sqlalchemy import select

from app.extensions import db
from app.models import Person, RoleType, Topic


def make_person(email="ada@example.com"):
    person = Person(display_name="Ada", email=email)
    person.add_role(RoleType.LEARNER)
    db.session.add(person)
    db.session.commit()
    return person


def run(app, *args):
    return app.test_cli_runner().invoke(args=list(args))


def test_grant_role_adds_the_role(app):
    person_id = make_person().id

    result = run(app, "grant-role", "ADA@example.com", "instructor")

    assert result.exit_code == 0
    db.session.expire_all()
    assert db.session.get(Person, person_id).has_role(RoleType.INSTRUCTOR)


def test_grant_role_fails_for_unknown_email(app):
    result = run(app, "grant-role", "nobody@example.com", "instructor")

    assert result.exit_code != 0
    assert "No account found" in result.output


def test_grant_role_rejects_unknown_role_names(app):
    make_person()

    result = run(app, "grant-role", "ada@example.com", "wizard")

    assert result.exit_code != 0


def test_granting_a_role_twice_is_harmless(app):
    make_person()
    run(app, "grant-role", "ada@example.com", "instructor")

    result = run(app, "grant-role", "ada@example.com", "instructor")

    assert result.exit_code == 0
    assert "already has" in result.output


def test_add_topic_creates_a_topic(app):
    result = run(app, "add-topic", "Strings", "--order", "1")

    topic = db.session.scalars(select(Topic)).one()
    assert result.exit_code == 0
    assert topic.slug == "strings"
    assert topic.sort_order == 1


def test_add_topic_rejects_duplicates(app):
    run(app, "add-topic", "Strings")

    result = run(app, "add-topic", "strings")

    assert result.exit_code != 0
    assert "already exists" in result.output