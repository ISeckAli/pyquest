"""
Admin pages: the user list, each user's page and the actions on it
(spec FR13), the audit log (PR-M1), and engagement reports with CSV export
(FR15). Actions are POST forms with CSRF tokens, and each redirects back
afterwards (Post/Redirect/Get), so refreshing never repeats one.
"""

from datetime import UTC, datetime

from flask import Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.admin import bp
from app.auth.decorators import role_required
from app.extensions import db
from app.models import Person, RoleType
from app.services.admin import (
    AdminError,
    audit_entries,
    grant_role,
    list_people,
    revoke_role,
    set_active,
)
from app.services.reports import (
    DEFAULT_PERIOD,
    PERIODS,
    engagement_summary,
    learners_csv,
)

ADMIN = RoleType.SYSTEM_ADMINISTRATOR

ROLE_LABELS = {
    RoleType.LEARNER: "Learner",
    RoleType.INSTRUCTOR: "Instructor",
    RoleType.SYSTEM_ADMINISTRATOR: "Administrator",
}

ACTION_LABELS = {
    "role.granted": "Role granted",
    "role.revoked": "Role removed",
    "account.deactivated": "Account deactivated",
    "account.reactivated": "Account reactivated",
}


def _person_or_404(person_id):
    person = db.session.get(Person, person_id)
    if person is None:
        abort(404)
    return person


def _role_or_400(value):
    """A role from a form or address, or 400 Bad Request if it is not one."""
    try:
        return RoleType(value)
    except ValueError:
        abort(400)


def _back_to(person):
    return redirect(url_for("admin.user", person_id=person.id))


# ---------------------------------------------------------------------------
# Users (FR13)
# ---------------------------------------------------------------------------

@bp.route("/users")
@role_required(ADMIN)
def users():
    """Everyone, searchable by name or email. Guests are hidden by default."""
    search = request.args.get("q", "").strip()
    include_guests = request.args.get("guests") == "1"
    return render_template(
        "admin/users.html",
        people=list_people(search, include_guests),
        search=search,
        include_guests=include_guests,
        role_labels=ROLE_LABELS,
    )


@bp.route("/users/<int:person_id>")
@role_required(ADMIN)
def user(person_id):
    """One person: details, roles, account status, and history."""
    person = _person_or_404(person_id)
    return render_template(
        "admin/user.html",
        person=person,
        missing_roles=[role for role in RoleType if not person.has_role(role)],
        history=audit_entries(limit=20, target=person),
        role_labels=ROLE_LABELS,
        action_labels=ACTION_LABELS,
        is_self=person.id == current_user.party_id,
    )


@bp.route("/users/<int:person_id>/roles", methods=["POST"])
@role_required(ADMIN)
def grant(person_id):
    person = _person_or_404(person_id)
    role = _role_or_400(request.form.get("role", ""))
    try:
        grant_role(current_user, person, role)
    except AdminError as error:
        flash(str(error), "error")
    else:
        flash(f"Granted the {ROLE_LABELS[role]} role to {person.display_name}.", "success")
    return _back_to(person)


@bp.route("/users/<int:person_id>/roles/<role>/revoke", methods=["POST"])
@role_required(ADMIN)
def revoke(person_id, role):
    person = _person_or_404(person_id)
    role = _role_or_400(role)
    try:
        revoke_role(current_user, person, role)
    except AdminError as error:
        flash(str(error), "error")
    else:
        flash(f"Removed the {ROLE_LABELS[role]} role from {person.display_name}.", "info")
    return _back_to(person)


@bp.route("/users/<int:person_id>/status", methods=["POST"])
@role_required(ADMIN)
def status(person_id):
    person = _person_or_404(person_id)
    active = request.form.get("active") == "1"
    try:
        set_active(current_user, person, active)
    except AdminError as error:
        flash(str(error), "error")
    else:
        flash(
            f"{person.display_name}'s account is now {'active' if active else 'deactivated'}.",
            "success" if active else "info",
        )
    return _back_to(person)


# ---------------------------------------------------------------------------
# Audit log (PR-M1) and reports (FR15)
# ---------------------------------------------------------------------------

@bp.route("/audit")
@role_required(ADMIN)
def audit():
    """Every administrative action, newest first."""
    return render_template(
        "admin/audit.html", entries=audit_entries(), action_labels=ACTION_LABELS
    )


def _period():
    """The report period from the address, or the default if not a valid one."""
    days = request.args.get("days", type=int)
    return days if days in PERIODS else DEFAULT_PERIOD


@bp.route("/reports")
@role_required(ADMIN)
def reports():
    """Engagement over the last 7, 30, or 90 days."""
    return render_template(
        "admin/reports.html", summary=engagement_summary(_period()), periods=PERIODS
    )


@bp.route("/reports/learners.csv")
@role_required(ADMIN)
def learners_export():
    """Download every registered learner's progress as a spreadsheet file."""
    filename = f"pyquest-learners-{datetime.now(UTC):%Y-%m-%d}.csv"
    return Response(
        learners_csv(),
        mimetype="text/csv",
        # attachment makes the browser download the file rather than show it.
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )