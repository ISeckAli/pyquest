"""
Administration (spec FR13, PR-M1): managing roles and accounts, with every
change recorded in the audit log.

Each action writes its audit entry in the same transaction as the change
itself, so the log can never miss a change or record one that did not
happen.
"""

from sqlalchemy import or_, select

from app.extensions import db
from app.models import AuditLog, LearnerProfile, Person, RoleType


class AdminError(Exception):
    """An administrative action was not allowed. The message is safe to show."""


def _record(actor, action, target=None, details=""):
    """Add an audit entry to the current transaction (the caller commits)."""
    db.session.add(
        AuditLog(
            actor_party_id=actor.party_id if actor is not None else None,
            action=action,
            target_party_id=target.id if target is not None else None,
            details=details,
        )
    )


def grant_role(actor, person, role_type):
    """Give a person a role, recording who granted it.

    Raises:
        AdminError: if the person already holds the role.
    """
    role_type = RoleType(role_type)
    if person.has_role(role_type):
        raise AdminError(f"{person.display_name} already has the {role_type.value} role.")

    person.add_role(role_type, granted_by=actor.party)
    # Learners need a profile for XP and streaks; accounts created as staff
    # do not have one yet.
    if role_type == RoleType.LEARNER and person.learner_profile is None:
        person.learner_profile = LearnerProfile(
            total_xp=0, level=1, current_streak=0, longest_streak=0
        )

    _record(actor, "role.granted", person, role_type.value)
    db.session.commit()


def revoke_role(actor, person, role_type):
    """Remove a role from a person. Their data is kept.

    Raises:
        AdminError: if they do not hold the role, or an administrator tries
            to remove their own administrator role (which could leave the
            site with no one able to manage it).
    """
    role_type = RoleType(role_type)
    role = next((r for r in person.roles if r.role_type == role_type), None)
    if role is None:
        raise AdminError(f"{person.display_name} does not have the {role_type.value} role.")
    if role_type == RoleType.SYSTEM_ADMINISTRATOR and person.id == actor.party_id:
        raise AdminError("You cannot remove your own administrator role.")

    # Removing it from the list deletes it (delete-orphan cascade).
    person.roles.remove(role)
    _record(actor, "role.revoked", person, role_type.value)
    db.session.commit()


def set_active(actor, person, active):
    """Deactivate or reactivate a person's account.

    A deactivated account is signed out on its next request and cannot log
    in; its data is kept (spec FR13).

    Raises:
        AdminError: if the person has no login account, or an administrator
            tries to deactivate their own account.
    """
    account = person.account
    if account is None:
        raise AdminError(f"{person.display_name} has no login account.")
    if not active and person.id == actor.party_id:
        raise AdminError("You cannot deactivate your own account.")
    if account.is_active == active:
        return

    account.is_active = active
    _record(actor, "account.reactivated" if active else "account.deactivated", person)
    db.session.commit()


def list_people(search="", include_guests=False):
    """People for the admin user list, matching a name or email search.

    Guests are hidden unless asked for: they are temporary and could
    otherwise crowd out real accounts.
    """
    statement = select(Person).order_by(Person.display_name, Person.id)
    if not include_guests:
        statement = statement.where(Person.is_guest.is_(False))

    search = (search or "").strip()
    if search:
        # icontains ignores capitals; autoescape treats % and _ in the
        # search text as ordinary characters rather than database wildcards.
        statement = statement.where(
            or_(
                Person.display_name.icontains(search, autoescape=True),
                Person.email.icontains(search, autoescape=True),
            )
        )
    return db.session.scalars(statement).all()


def audit_entries(limit=200, target=None):
    """The most recent audit entries, newest first; only about one person
    when target is given."""
    statement = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if target is not None:
        statement = statement.where(AuditLog.target_party_id == target.id)
    return db.session.scalars(statement.limit(limit)).all()