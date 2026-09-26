"""
Challenge models: the coding problems learners solve (spec section 7, FR04,
FR06, FR12).

    Topic           a group of related challenges, in a recommended order
    Challenge       one coding problem, with its lifecycle status
    TestCase        one graded input and expected output for a challenge
    FallbackHint    an instructor-written hint used when the AI Coach is
                    unavailable (NFR05)

The SRS Challenge stored a single expectedOutput. PyQuest grades against
several test cases instead (decision DR-06), some of them hidden, so a
learner cannot pass by printing the answer to the examples they can see.
"""

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.identity import utc_now


def _enum_type(enum_class):
    """Column type that stores an enum's readable value ("beginner").

    Same approach as Role.role_type: plain text rather than a database-
    specific enum type, so the column works identically on SQLite and
    Postgres.
    """
    return Enum(
        enum_class,
        native_enum=False,
        length=20,
        values_callable=lambda members: [member.value for member in members],
    )


class Difficulty(StrEnum):
    """Challenge difficulty levels (spec FR04), from easiest to hardest."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

    @property
    def rank(self):
        """Position from easiest (0) to hardest, for sorting."""
        return list(Difficulty).index(self)

    @property
    def label(self):
        """Display form, such as "Beginner"."""
        return self.value.title()


class ChallengeStatus(StrEnum):
    """Lifecycle states from the SRS Challenge state diagram (Part C, Figure 7).

    Draft -> Published <-> Unpublished. Deletion is allowed only from Draft
    or Unpublished, so a challenge learners can currently see never
    disappears without first being unpublished.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"


class Topic(db.Model):
    """A group of related challenges, such as "Strings" or "Loops" (PR-L1).

    sort_order sets the recommended learning path: lower numbers come first.
    """

    __tablename__ = "topic"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)

    # The URL-friendly form of the name, used in library filter links.
    slug: Mapped[str] = mapped_column(String(60), unique=True)

    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(default=0)

    challenges: Mapped[list["Challenge"]] = relationship(back_populates="topic")

    def __repr__(self):
        return f"<Topic {self.slug}>"


class Challenge(db.Model):
    """One coding problem (SRS Challenge)."""

    __tablename__ = "challenge"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))

    # Used in the challenge's URL. Set once at creation and never changed,
    # so links and bookmarks keep working even if the title is edited.
    slug: Mapped[str] = mapped_column(String(140), unique=True)

    # The problem statement shown to learners.
    description: Mapped[str] = mapped_column(Text)

    topic_id: Mapped[int] = mapped_column(ForeignKey("topic.id"))
    difficulty: Mapped[Difficulty] = mapped_column(_enum_type(Difficulty))
    xp_value: Mapped[int] = mapped_column()

    # Code pre-filled in the learner's editor.
    starter_code: Mapped[str] = mapped_column(Text, default="")

    # A correct solution, used to check the tests before publishing. Never
    # shown to learners and never sent to the AI Coach (spec section 5.9).
    reference_solution: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[ChallengeStatus] = mapped_column(
        _enum_type(ChallengeStatus), default=ChallengeStatus.DRAFT
    )

    # The instructor who wrote it. Empty for challenges loaded by the seed
    # script, which have no individual author.
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("party.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    # When the challenge was first published. Kept if it is unpublished and
    # published again, so it always records the original release.
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    topic: Mapped["Topic"] = relationship(back_populates="challenges")
    author: Mapped[Optional["Party"]] = relationship()  # noqa: F821

    test_cases: Mapped[list["TestCase"]] = relationship(
        back_populates="challenge",
        cascade="all, delete-orphan",
        order_by="TestCase.sort_order",
    )
    fallback_hints: Mapped[list["FallbackHint"]] = relationship(
        back_populates="challenge",
        cascade="all, delete-orphan",
        order_by="FallbackHint.sort_order",
    )

    @property
    def visible_tests(self):
        """Test cases shown to learners as worked examples."""
        return [test for test in self.test_cases if not test.is_hidden]

    @property
    def hidden_tests(self):
        """Test cases used for grading but never shown to learners."""
        return [test for test in self.test_cases if test.is_hidden]

    @property
    def is_published(self):
        return self.status == ChallengeStatus.PUBLISHED

    def __repr__(self):
        return f"<Challenge {self.slug} {self.status}>"


class TestCase(db.Model):
    """One graded run of a challenge: input given, output expected (DR-06)."""

    # pytest treats any class whose name starts with "Test" as a group of
    # tests. This tells it that this model is not one, so importing it into
    # a test file does not produce collection warnings.
    __test__ = False

    __tablename__ = "test_case"

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenge.id"))

    # Text supplied to the program's standard input (what input() reads).
    input_data: Mapped[str] = mapped_column(Text, default="")

    # The exact text the program must print.
    expected_output: Mapped[str] = mapped_column(Text)

    # Hidden tests are never sent to the browser as examples or to the AI
    # Coach, so their answers cannot be read or leaked (spec FR06, 5.9).
    is_hidden: Mapped[bool] = mapped_column(default=False)

    sort_order: Mapped[int] = mapped_column(default=0)

    challenge: Mapped["Challenge"] = relationship(back_populates="test_cases")

    def __repr__(self):
        kind = "hidden" if self.is_hidden else "visible"
        return f"<TestCase {self.id} {kind} challenge={self.challenge_id}>"


class FallbackHint(db.Model):
    """An instructor-written hint shown when the AI Coach is unavailable."""

    __tablename__ = "fallback_hint"

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenge.id"))
    text: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(default=0)

    challenge: Mapped["Challenge"] = relationship(back_populates="fallback_hints")

    def __repr__(self):
        return f"<FallbackHint {self.id} challenge={self.challenge_id}>"