"""
Forms for registration and login.

Forms check the shape of the input: required fields are filled in, the email
looks like an email, and the two password fields match. The rules about
what is allowed (password strength, duplicate emails, lockouts) live in the
authentication service (app/services/auth.py), so each rule is defined in
exactly one place.

Every FlaskForm includes a hidden CSRF token automatically (spec PR-N2).

The autocomplete hints tell browsers and password managers what each field
is for, so they can offer to fill in or generate passwords correctly. They
also help assistive technology describe the fields (WCAG 2.1).
"""

from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

from app.services.auth import DISPLAY_NAME_MAX_LENGTH, DISPLAY_NAME_MIN_LENGTH

# Email() checks only the format of the address. check_deliverability=False
# stops it from looking up the domain on the internet, which would slow
# every sign-up and make tests fail without a network connection.
EMAIL_FORMAT = Email(
    message="Enter a valid email address.", check_deliverability=False
)


class RegistrationForm(FlaskForm):
    """Sign-up form for new learners (spec FR01)."""

    display_name = StringField(
        "Display name",
        validators=[
            DataRequired(message="Enter a display name."),
            Length(
                min=DISPLAY_NAME_MIN_LENGTH,
                max=DISPLAY_NAME_MAX_LENGTH,
                message=(
                    f"Display name must be {DISPLAY_NAME_MIN_LENGTH} to "
                    f"{DISPLAY_NAME_MAX_LENGTH} characters long."
                ),
            ),
        ],
        render_kw={"autocomplete": "nickname"},
    )

    email = EmailField(
        "Email",
        validators=[
            DataRequired(message="Enter your email address."),
            EMAIL_FORMAT,
            Length(max=254),
        ],
        render_kw={"autocomplete": "email"},
    )

    # Strength rules are applied by the authentication service, not here.
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Enter a password.")],
        render_kw={"autocomplete": "new-password"},
    )

    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(message="Enter your password again."),
            EqualTo("password", message="The passwords do not match."),
        ],
        render_kw={"autocomplete": "new-password"},
    )

    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    """Login form (spec FR02).

    There is deliberately no "remember me" option: sessions end after 30
    minutes of inactivity (NFR03), and a long-lived login cookie would
    bypass that.
    """

    email = EmailField(
        "Email",
        validators=[DataRequired(message="Enter your email address."), EMAIL_FORMAT],
        render_kw={"autocomplete": "email"},
    )

    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Enter your password.")],
        render_kw={"autocomplete": "current-password"},
    )

    submit = SubmitField("Log in")