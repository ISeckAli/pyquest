"""
Views for writing and publishing challenges (spec FR12).

Actions that change data (publish, unpublish, delete, add or remove a test)
are POST requests with CSRF tokens, and each redirects back to a page
afterwards (Post/Redirect/Get), so refreshing never repeats an action.
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.decorators import role_required
from app.extensions import db
from app.instructor import bp
from app.instructor.forms import ChallengeForm, TestCaseForm
from app.models import Challenge, RoleType, TestCase, Topic
from app.services.challenges import (
    ChallengeError,
    add_test_case,
    can_manage,
    create_challenge,
    delete_challenge,
    list_manageable,
    list_topics,
    publish,
    publish_problems,
    remove_test_case,
    set_fallback_hints,
    unpublish,
    update_challenge,
)

AUTHOR_ROLES = (RoleType.INSTRUCTOR, RoleType.SYSTEM_ADMINISTRATOR)

# Where the service's field names differ from the form's field names.
FORM_FIELD_FOR = {"topic": "topic_id", "fallback_hints": "hint_1"}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@bp.route("/challenges")
@role_required(*AUTHOR_ROLES)
def challenge_list():
    """The challenges this account may manage."""
    return render_template(
        "instructor/challenges.html",
        challenges=list_manageable(current_user),
        is_admin=current_user.has_role(RoleType.SYSTEM_ADMINISTRATOR),
    )


@bp.route("/challenges/new", methods=["GET", "POST"])
@role_required(*AUTHOR_ROLES)
def new_challenge():
    """Create a challenge as a draft, then continue to its edit page."""
    form = ChallengeForm()
    topics = _set_topic_choices(form)

    if form.validate_on_submit():
        try:
            challenge = create_challenge(
                current_user,
                form.title.data,
                form.description.data,
                db.session.get(Topic, form.topic_id.data),
                form.difficulty.data,
                form.starter_code.data,
                form.reference_solution.data,
                form.xp_value.data,
            )
            set_fallback_hints(challenge, form.hint_texts)
        except ChallengeError as error:
            _show_error(form, error)
        else:
            flash("Draft created. Add test cases, then publish when it is ready.", "success")
            return redirect(url_for("instructor.edit_challenge", challenge_id=challenge.id))

    return render_template("instructor/new.html", form=form, has_topics=bool(topics))


@bp.route("/challenges/<int:challenge_id>/edit", methods=["GET", "POST"])
@role_required(*AUTHOR_ROLES)
def edit_challenge(challenge_id):
    """Edit details and hints, manage test cases, and publish."""
    challenge = _manageable_or_abort(challenge_id)

    # obj=challenge pre-fills the fields on the first visit; submitted
    # values take priority on a POST.
    form = ChallengeForm(obj=challenge)
    _set_topic_choices(form)

    if request.method == "GET":
        hint_fields = (form.hint_1, form.hint_2, form.hint_3)
        for field, hint in zip(hint_fields, challenge.fallback_hints):
            field.data = hint.text

    if form.validate_on_submit():
        try:
            update_challenge(
                challenge,
                form.title.data,
                form.description.data,
                db.session.get(Topic, form.topic_id.data),
                form.difficulty.data,
                form.starter_code.data,
                form.reference_solution.data,
                form.xp_value.data,
            )
            set_fallback_hints(challenge, form.hint_texts)
        except ChallengeError as error:
            _show_error(form, error)
        else:
            flash("Changes saved.", "success")
            return redirect(url_for("instructor.edit_challenge", challenge_id=challenge.id))

    return render_template(
        "instructor/edit.html",
        challenge=challenge,
        form=form,
        test_form=TestCaseForm(prefix="test"),
        problems=publish_problems(challenge),
    )


@bp.route("/challenges/<int:challenge_id>/preview")
@role_required(*AUTHOR_ROLES)
def preview_challenge(challenge_id):
    """Show the challenge exactly as learners will see it, even as a draft."""
    challenge = _manageable_or_abort(challenge_id)
    return render_template("challenges/detail.html", challenge=challenge, preview=True)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@bp.route("/challenges/<int:challenge_id>/tests", methods=["POST"])
@role_required(*AUTHOR_ROLES)
def add_test(challenge_id):
    challenge = _manageable_or_abort(challenge_id)
    form = TestCaseForm(prefix="test")

    if form.validate_on_submit():
        try:
            add_test_case(
                challenge,
                form.input_data.data,
                form.expected_output.data,
                form.is_hidden.data,
            )
        except ChallengeError as error:
            _flash_error(error)
        else:
            flash("Test case added.", "success")
    else:
        flash(_first_form_error(form), "error")

    return _back_to_tests(challenge)


@bp.route("/challenges/<int:challenge_id>/tests/<int:test_id>/delete", methods=["POST"])
@role_required(*AUTHOR_ROLES)
def remove_test(challenge_id, test_id):
    challenge = _manageable_or_abort(challenge_id)
    test_case = db.session.get(TestCase, test_id)

    # The test must belong to this challenge. Without this check, someone
    # allowed to manage one challenge could change the test id in the
    # address to delete another challenge's tests (an "insecure direct
    # object reference").
    if test_case is None or test_case.challenge_id != challenge.id:
        abort(404)

    try:
        remove_test_case(test_case)
    except ChallengeError as error:
        _flash_error(error)
    else:
        flash("Test case removed.", "success")

    return _back_to_tests(challenge)


@bp.route("/challenges/<int:challenge_id>/publish", methods=["POST"])
@role_required(*AUTHOR_ROLES)
def publish_challenge(challenge_id):
    challenge = _manageable_or_abort(challenge_id)
    try:
        publish(challenge)
    except ChallengeError as error:
        _flash_error(error)
    else:
        flash("Published. Learners can now find this challenge in the library.", "success")
    return redirect(url_for("instructor.edit_challenge", challenge_id=challenge.id))


@bp.route("/challenges/<int:challenge_id>/unpublish", methods=["POST"])
@role_required(*AUTHOR_ROLES)
def unpublish_challenge(challenge_id):
    challenge = _manageable_or_abort(challenge_id)
    try:
        unpublish(challenge)
    except ChallengeError as error:
        _flash_error(error)
    else:
        flash("Unpublished. Learners can no longer see this challenge.", "info")
    return redirect(url_for("instructor.edit_challenge", challenge_id=challenge.id))


@bp.route("/challenges/<int:challenge_id>/delete", methods=["POST"])
@role_required(*AUTHOR_ROLES)
def delete_challenge_route(challenge_id):
    challenge = _manageable_or_abort(challenge_id)
    try:
        delete_challenge(challenge)
    except ChallengeError as error:
        _flash_error(error)
        return redirect(url_for("instructor.edit_challenge", challenge_id=challenge.id))

    flash("Challenge deleted.", "info")
    return redirect(url_for("instructor.challenge_list"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _manageable_or_abort(challenge_id):
    """Return the challenge, or stop with 404 (no such challenge) or 403
    (this account may not manage it)."""
    challenge = db.session.get(Challenge, challenge_id)
    if challenge is None:
        abort(404)
    if not can_manage(current_user, challenge):
        abort(403)
    return challenge


def _set_topic_choices(form):
    topics = list_topics()
    form.topic_id.choices = [(topic.id, topic.name) for topic in topics]
    return topics


def _show_error(form, error):
    """Show a service error beside its form field, or as a flash message."""
    field_name = FORM_FIELD_FOR.get(error.field, error.field)
    field = getattr(form, field_name, None) if field_name else None
    if field is not None:
        field.errors.append(str(error))
    else:
        _flash_error(error)


def _flash_error(error):
    """Flash a service error, including every unmet requirement if listed."""
    message = " ".join([str(error), *error.problems])
    flash(message, "error")


def _first_form_error(form):
    for errors in form.errors.values():
        if errors:
            return errors[0]
    return "Check the form and try again."


def _back_to_tests(challenge):
    """Return to the edit page, scrolled to the test cases section."""
    return redirect(
        url_for("instructor.edit_challenge", challenge_id=challenge.id, _anchor="tests")
    )