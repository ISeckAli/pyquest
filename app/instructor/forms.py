"""
Forms for writing challenges and their test cases (spec FR12).

As with the other forms, these check the shape of the input; the rules
(publishing requirements, XP limits, hint limits) live in the challenge
service, so each rule is defined in one place.
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models import Difficulty
from app.services.challenges import TITLE_MAX_LENGTH, TITLE_MIN_LENGTH, XP_MAX, XP_MIN

# Settings for fields that hold code: a monospace font (see instructor.css)
# and no spell-checking, auto-capitalising, or autocomplete, all of which
# would otherwise "correct" Python code as it is typed.
CODE_FIELD = {
    "class": "code-input",
    "spellcheck": "false",
    "autocapitalize": "off",
    "autocomplete": "off",
    "rows": 8,
}

SHORT_CODE_FIELD = {**CODE_FIELD, "rows": 3}


class ChallengeForm(FlaskForm):
    """Create or edit a challenge's details and fallback hints.

    Field names match the Challenge attributes, so the edit page can
    pre-fill the form directly from the challenge. Topic choices are
    supplied by the view.
    """

    title = StringField(
        "Title",
        validators=[
            DataRequired(message="Enter a title."),
            Length(
                min=TITLE_MIN_LENGTH,
                max=TITLE_MAX_LENGTH,
                message=f"Title must be {TITLE_MIN_LENGTH} to {TITLE_MAX_LENGTH} characters long.",
            ),
        ],
    )

    topic_id = SelectField(
        "Topic", coerce=int, validators=[DataRequired(message="Choose a topic.")]
    )

    difficulty = SelectField(
        "Difficulty", choices=[(level.value, level.label) for level in Difficulty]
    )

    # Optional: left blank, the default XP for the difficulty is used.
    xp_value = IntegerField(
        "XP value",
        validators=[
            Optional(),
            NumberRange(
                min=XP_MIN,
                max=XP_MAX,
                message=f"XP must be a whole number from {XP_MIN} to {XP_MAX}.",
            ),
        ],
    )

    description = TextAreaField(
        "Problem description",
        validators=[DataRequired(message="Describe the problem the learner must solve.")],
        render_kw={"rows": 8},
    )

    starter_code = TextAreaField("Starter code", render_kw=CODE_FIELD)
    reference_solution = TextAreaField("Reference solution", render_kw=CODE_FIELD)

    # Three fields match CHALLENGE_MAX_FALLBACK_HINTS in config.py.
    hint_1 = TextAreaField("Fallback hint 1", render_kw={"rows": 2})
    hint_2 = TextAreaField("Fallback hint 2", render_kw={"rows": 2})
    hint_3 = TextAreaField("Fallback hint 3", render_kw={"rows": 2})

    submit = SubmitField("Save challenge")

    @property
    def hint_texts(self):
        """The three hint boxes as a list; blank ones are dropped by the service."""
        return [self.hint_1.data, self.hint_2.data, self.hint_3.data]


class TestCaseForm(FlaskForm):
    """Add one test case to a challenge."""

    # The class name starts with "Test", so this stops pytest from treating
    # it as a group of tests if it is ever imported into a test file.
    __test__ = False

    input_data = TextAreaField("Input (what input() reads)", render_kw=SHORT_CODE_FIELD)

    expected_output = TextAreaField(
        "Expected output",
        validators=[DataRequired(message="Enter the output the program should print.")],
        render_kw=SHORT_CODE_FIELD,
    )

    is_hidden = BooleanField("Hidden test (used for grading, never shown to learners)")

    submit = SubmitField("Add test case")