"""
Tests for the audit log page, engagement reports, and the CSV export
(spec FR15, PR-M1).
"""

import csv
import io
from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.models import LearnerProfile, Person, RoleType, Submission, SubmissionStatus, UserAccount
from app.services.admin import grant_role
from app.services.challenges import create_challenge, create_topic
from app.services.guest import create_guest
from app.services.reports import engagement_summary, learners_csv

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def make_account(email, *roles, name=None, xp=0, created=None):
    person = Person(display_name=name or email.split("@")[0].title(), email=email)
    if created is not None:
        person.created_at = created
    for role in roles:
        person.add_role(role)
    account = UserAccount(party=person)
    account.password_hash = "not-used-in-these-tests"
    db.session.add(account)
    if RoleType.LEARNER in roles:
        db.session.add(LearnerProfile(person=person, total_xp=xp, level=1, current_streak=0, longest_streak=0))
    db.session.commit()
    return account


def sign_in(client, account):
    """Sign an account in directly (see test_instructor_routes.py)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(account.id)
        session["_fresh"] = True


def submit(account, challenge, passed, when):
    db.session.add(
        Submission(
            party_id=account.party_id, challenge_id=challenge.id, code="x",
            status=SubmissionStatus.PASSED if passed else SubmissionStatus.FAILED,
            passed_count=1, total_count=1, submitted_at=when,
        )
    )
    db.session.commit()


@pytest.fixture
def challenge(app):
    return create_challenge(None, "One", "Solve it.", create_topic("Strings", sort_order=1), "beginner")


@pytest.fixture
def admin(client):
    account = make_account("admin@example.com", RoleType.SYSTEM_ADMINISTRATOR)
    sign_in(client, account)
    return account


def test_engagement_summary_counts_the_period_and_leaves_out_guests(app, challenge):
    ada = make_account("ada@example.com", RoleType.LEARNER, created=NOW - timedelta(days=3))
    make_account("old@example.com", RoleType.LEARNER, created=NOW - timedelta(days=60))
    guest = create_guest()
    guest.party.created_at = NOW - timedelta(days=1)
    db.session.commit()
    submit(ada, challenge, True, NOW - timedelta(days=1))
    submit(ada, challenge, False, NOW - timedelta(days=2))
    submit(ada, challenge, True, NOW - timedelta(days=45))  # before the period
    submit(guest, challenge, True, NOW - timedelta(days=1))  # guests are left out

    summary = engagement_summary(30, NOW)

    assert summary["learners"] == 2
    assert summary["new_learners"] == 1
    assert summary["active_learners"] == 1
    assert summary["guests"] == 1
    assert (summary["submissions"], summary["solves"], summary["pass_rate"]) == (2, 1, 50)


def test_learner_export_has_a_row_per_registered_learner(app, challenge):
    ada = make_account("ada@example.com", RoleType.LEARNER, name="Ada", xp=40)
    make_account("grace@example.com", RoleType.LEARNER, name="Grace", xp=10)
    create_guest()
    submit(ada, challenge, True, NOW)
    submit(ada, challenge, True, NOW)

    rows = list(csv.reader(io.StringIO(learners_csv())))

    assert rows[0][:2] == ["Name", "Email"]
    assert [row[0] for row in rows[1:]] == ["Ada", "Grace"]
    assert rows[1][5:7] == ["1", "2"]  # 1 challenge solved, 2 submissions


def test_spreadsheet_formulas_in_names_are_neutralised(app):
    make_account("evil@example.com", RoleType.LEARNER, name='=HYPERLINK("http://evil.example")')

    rows = list(csv.reader(io.StringIO(learners_csv())))

    assert rows[1][0].startswith("'=")


def test_reports_page_and_download_are_for_administrators(client, admin):
    page = client.get("/admin/reports?days=7")
    download = client.get("/admin/reports/learners.csv")

    assert b"Last 7 days" in page.data
    assert download.mimetype == "text/csv"
    assert "attachment" in download.headers["Content-Disposition"]

    sign_in(client, make_account("ada@example.com", RoleType.LEARNER))
    assert client.get("/admin/reports").status_code == 403
    assert client.get("/admin/reports/learners.csv").status_code == 403


def test_an_unknown_period_falls_back_to_30_days(client, admin):
    html = client.get("/admin/reports?days=999").get_data(as_text=True)

    assert 'aria-current="page">Last 30 days' in html


def test_audit_log_page_lists_actions(client, admin):
    ada = make_account("ada@example.com", RoleType.LEARNER)
    grant_role(admin, ada.party, "instructor")

    html = client.get("/admin/audit").get_data(as_text=True)

    assert "Role granted: instructor" in html
    assert "Admin" in html and "Ada" in html