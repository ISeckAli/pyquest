"""
Tests for administration (spec FR13, PR-M1): roles, account status,
safeguards, search, and the audit log.
"""

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import AuditLog, Person, Role, RoleType, UserAccount
from app.models.identity import load_user
from app.services.admin import (
    AdminError,
    audit_entries,
    grant_role,
    list_people,
    revoke_role,
    set_active,
)
from app.services.guest import create_guest


def make_account(email, *roles):
    person = Person(display_name=email.split("@")[0].title(), email=email)
    for role in roles:
        person.add_role(role)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add_all([person, account])
    db.session.commit()
    return account


@pytest.fixture
def admin(app):
    return make_account("admin@example.com", RoleType.SYSTEM_ADMINISTRATOR)


@pytest.fixture
def ada(app):
    return make_account("ada@example.com", RoleType.LEARNER)


def test_granting_a_role_records_who_granted_it(admin, ada):
    grant_role(admin, ada.party, "instructor")

    role = db.session.scalars(select(Role).where(Role.role_type == RoleType.INSTRUCTOR)).one()
    entry = audit_entries()[0]
    assert ada.has_role(RoleType.INSTRUCTOR)
    assert role.granted_by_party_id == admin.party_id
    assert (entry.action, entry.details, entry.target_party_id) == (
        "role.granted", "instructor", ada.party_id,
    )


def test_granting_a_role_they_already_have_is_refused(admin, ada):
    with pytest.raises(AdminError):
        grant_role(admin, ada.party, "learner")


def test_granting_the_learner_role_creates_a_profile(admin):
    teacher = make_account("teach@example.com", RoleType.INSTRUCTOR)

    grant_role(admin, teacher.party, "learner")

    assert teacher.party.learner_profile is not None


def test_revoking_a_role_is_recorded(admin):
    teacher = make_account("teach@example.com", RoleType.INSTRUCTOR)

    revoke_role(admin, teacher.party, "instructor")

    assert not teacher.has_role(RoleType.INSTRUCTOR)
    assert audit_entries()[0].action == "role.revoked"


def test_admins_cannot_remove_their_own_admin_role(admin):
    with pytest.raises(AdminError, match="your own"):
        revoke_role(admin, admin.party, "system_administrator")

    assert admin.has_role(RoleType.SYSTEM_ADMINISTRATOR)


def test_deactivated_accounts_are_signed_out_and_can_be_restored(admin, ada):
    set_active(admin, ada.party, False)

    assert load_user(str(ada.id)) is None
    assert audit_entries()[0].action == "account.deactivated"

    set_active(admin, ada.party, True)

    assert load_user(str(ada.id)) is not None
    assert audit_entries()[0].action == "account.reactivated"


def test_admins_cannot_deactivate_themselves(admin):
    with pytest.raises(AdminError):
        set_active(admin, admin.party, False)


def test_people_can_be_searched_by_name_or_email_without_guests(admin, ada):
    make_account("grace@example.com", RoleType.LEARNER)
    create_guest()

    assert [p.email for p in list_people("ADA")] == ["ada@example.com"]
    assert [p.email for p in list_people("grace@")] == ["grace@example.com"]
    assert len(list_people()) == 3
    assert len(list_people(include_guests=True)) == 4


def test_nothing_is_logged_when_an_action_is_refused(admin, ada):
    with pytest.raises(AdminError):
        grant_role(admin, ada.party, "learner")

    assert db.session.scalars(select(AuditLog)).all() == []