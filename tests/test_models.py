"""
Tests for the identity models (spec section 4.1 and section 7).

Each test runs against a fresh in-memory database created by the `app`
fixture in conftest.py. Tests that only need the database still request
`app`, because it provides the application context the database requires.

New objects are always added to the session explicitly with
db.session.add(). SQLAlchemy 2.x does not save an object just because it
was linked to one that is already saved, so relying on that would leave
objects unsaved. Tests also reload data from the database after committing,
so they prove data was really stored rather than checking Python objects
that only exist in memory.
"""

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import LearnerProfile, Party, Person, Role, RoleType, UserAccount


def make_person(email="ada@example.com", display_name="Ada"):
    """Create, save, and return a Person, to keep tests short."""
    person = Person(display_name=display_name, email=email)
    db.session.add(person)
    db.session.commit()
    return person


def count_rows(model):
    """Return how many rows a model's table holds in the database."""
    return db.session.scalar(select(func.count()).select_from(model))


# ---------------------------------------------------------------------------
# Party and Person
# ---------------------------------------------------------------------------

def test_person_is_stored_as_a_party(app):
    """Joined-table inheritance: a Person loads back through Party."""
    person = make_person()
    db.session.expire_all()

    loaded = db.session.get(Party, person.id)

    assert isinstance(loaded, Person)
    assert loaded.party_type == "person"


def test_email_is_stored_trimmed_and_lowercase(app):
    person = make_person(email="  Ada@Example.COM ")
    db.session.expire_all()

    assert db.session.get(Person, person.id).email == "ada@example.com"


def test_email_is_unique_regardless_of_capitals(app):
    """FR01: one account per email address, however it is typed."""
    make_person(email="ada@example.com")

    db.session.add(Person(display_name="Other Ada", email="ADA@example.com"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_new_person_has_default_preferences(app):
    person = make_person()
    db.session.expire_all()

    loaded = db.session.get(Person, person.id)

    assert loaded.timezone == "America/Toronto"
    assert loaded.leaderboard_visible is True


# ---------------------------------------------------------------------------
# UserAccount
# ---------------------------------------------------------------------------

def test_password_is_hashed_and_can_be_checked(app):
    """NFR03: the stored value is a hash, never the password itself."""
    person = make_person()
    account = UserAccount(party=person)
    account.set_password("correct horse battery")
    db.session.add(account)
    db.session.commit()
    db.session.expire_all()

    stored = db.session.scalars(select(UserAccount)).one()

    assert stored.party_id == person.id
    assert stored.password_hash != "correct horse battery"
    assert stored.check_password("correct horse battery") is True
    assert stored.check_password("wrong password") is False


def test_new_account_is_active_with_no_failed_logins(app):
    person = make_person()
    account = UserAccount(party=person)
    account.set_password("correct horse battery")
    db.session.add(account)
    db.session.commit()
    db.session.expire_all()

    stored = db.session.scalars(select(UserAccount)).one()

    assert stored.is_active is True
    assert stored.failed_login_count == 0
    assert stored.locked_until is None
    assert stored.email_verified_at is None


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

def test_person_can_hold_several_roles(app):
    """The Party and Role pattern: one person, more than one role."""
    person = make_person()
    person.add_role(RoleType.LEARNER)
    person.add_role(RoleType.INSTRUCTOR)
    db.session.commit()
    db.session.expire_all()

    loaded = db.session.get(Person, person.id)

    assert loaded.has_role(RoleType.LEARNER)
    assert loaded.has_role(RoleType.INSTRUCTOR)
    assert not loaded.has_role(RoleType.SYSTEM_ADMINISTRATOR)
    assert count_rows(Role) == 2


def test_role_is_stored_as_readable_value(app):
    """The database holds "learner", not the Python name "LEARNER"."""
    person = make_person()
    person.add_role(RoleType.LEARNER)
    db.session.commit()

    stored = db.session.execute(text("SELECT role_type FROM role")).scalar_one()

    assert stored == "learner"


def test_same_role_cannot_be_added_twice(app):
    person = make_person()
    person.add_role(RoleType.LEARNER)

    with pytest.raises(ValueError):
        person.add_role(RoleType.LEARNER)


def test_database_rejects_duplicate_role_directly(app):
    """The unique constraint protects the data even if code skips add_role."""
    person = make_person()
    db.session.add(Role(party_id=person.id, role_type=RoleType.LEARNER))
    db.session.add(Role(party_id=person.id, role_type=RoleType.LEARNER))

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_role_records_who_granted_it(app):
    """FR13 and PR-M1: role changes are accountable."""
    admin = make_person(email="admin@example.com", display_name="Admin")
    learner = make_person(email="learner@example.com", display_name="Learner")

    learner.add_role(RoleType.INSTRUCTOR, granted_by=admin)
    db.session.commit()
    db.session.expire_all()

    stored = db.session.scalars(select(Role)).one()

    assert stored.party_id == learner.id
    assert stored.granted_by_party_id == admin.id


# ---------------------------------------------------------------------------
# LearnerProfile
# ---------------------------------------------------------------------------

def test_new_learner_profile_starts_at_zero(app):
    person = make_person()
    db.session.add(LearnerProfile(person=person))
    db.session.commit()
    db.session.expire_all()

    profile = db.session.get(LearnerProfile, person.id)

    assert profile.total_xp == 0
    assert profile.level == 1
    assert profile.current_streak == 0
    assert profile.longest_streak == 0
    assert profile.last_active_date is None


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

def test_deleting_person_removes_account_roles_and_profile(app):
    """Nothing is left behind when a person is deleted (spec PR-A6)."""
    person = make_person()
    account = UserAccount(party=person)
    account.set_password("correct horse battery")
    db.session.add(account)
    db.session.add(LearnerProfile(person=person))
    person.add_role(RoleType.LEARNER)
    db.session.commit()

    # Prove every row exists first, so the test cannot pass on empty tables.
    assert count_rows(Person) == 1
    assert count_rows(UserAccount) == 1
    assert count_rows(Role) == 1
    assert count_rows(LearnerProfile) == 1

    db.session.delete(person)
    db.session.commit()

    assert count_rows(Party) == 0
    assert count_rows(Person) == 0
    assert count_rows(UserAccount) == 0
    assert count_rows(Role) == 0
    assert count_rows(LearnerProfile) == 0