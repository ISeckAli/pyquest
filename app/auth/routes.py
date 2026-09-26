"""
Views for registration, login, and logout.
"""

from urllib.parse import urlsplit

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm
from app.services.auth import AuthError, RegistrationError, authenticate, register_learner

# Where users land after signing in or registering.
HOME_ENDPOINT = "learner.dashboard"


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Show the sign-up form and create a learner account (spec FR01)."""
    if current_user.is_authenticated:
        return redirect(url_for(HOME_ENDPOINT))

    form = RegistrationForm()

    # validate_on_submit() is True only for a POST whose fields pass the
    # form's checks (and whose CSRF token is valid).
    if form.validate_on_submit():
        try:
            account = register_learner(
                form.display_name.data, form.email.data, form.password.data
            )
        except RegistrationError as error:
            # Show the service's message beside the field it concerns.
            getattr(form, error.field).errors.append(str(error))
        else:
            _start_session(account)
            flash("Welcome to PyQuest! Your account is ready.", "success")
            return redirect(url_for(HOME_ENDPOINT))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Show the login form and sign the user in (spec FR02)."""
    if current_user.is_authenticated:
        return redirect(url_for(HOME_ENDPOINT))

    form = LoginForm()
    login_error = None

    if form.validate_on_submit():
        try:
            account = authenticate(form.email.data, form.password.data)
        except AuthError as error:
            # One message for the whole form, never tied to a single field,
            # so it cannot hint whether the email or the password was wrong.
            login_error = str(error)
        else:
            _start_session(account)
            target = _safe_redirect_target(request.args.get("next"))
            return redirect(target or url_for(HOME_ENDPOINT))

    return render_template("auth/login.html", form=form, login_error=login_error)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Sign the user out.

    POST only: a plain logout link could be triggered by another website
    (for example through a hidden image), signing users out without their
    knowledge. A POST form carries a CSRF token, so it cannot be forged.
    """
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


def _start_session(account):
    """Sign an account in with a fresh session.

    Clearing the session first means nothing stored before login carries
    over into the signed-in session. Marking the session permanent applies
    PERMANENT_SESSION_LIFETIME, the 30-minute inactivity timeout (NFR03).
    """
    session.clear()
    login_user(account)
    session.permanent = True


def _safe_redirect_target(target):
    """Return target only if it is a path within this site, otherwise None.

    Login pages commonly accept ?next=... to return users to the page they
    were trying to reach. Without this check, an attacker could share a
    link such as /login?next=https://evil.example so that, after a genuine
    login, the user lands on a fake site. Only relative paths that start
    with a single "/" are accepted.
    """
    if not target:
        return None
    # Browsers treat a backslash like a forward slash, so "/\evil.example"
    # would be read as "//evil.example", another website.
    if "\\" in target:
        return None

    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/"):
        return None
    return target