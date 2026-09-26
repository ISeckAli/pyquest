"""
Database models for PyQuest.

Every model is imported here so that importing this one package registers
all tables with SQLAlchemy. The application factory imports it, which is
what lets Flask-Migrate detect schema changes and lets tests create every
table with db.create_all().

Models are split into modules by feature area, matching the blueprint
structure: identity (people, accounts, roles) and challenge (topics,
challenges, test cases, fallback hints). Submissions and the AI Coach
follow in later parts.
"""

from app.models.challenge import (
    Challenge,
    ChallengeStatus,
    Difficulty,
    FallbackHint,
    TestCase,
    Topic,
)
from app.models.identity import (
    LearnerProfile,
    Party,
    Person,
    Role,
    RoleType,
    UserAccount,
)

# The public names of this package. Listing them documents what other code
# is expected to import, and tells linters these imports are intentional.
__all__ = [
    "Challenge",
    "ChallengeStatus",
    "Difficulty",
    "FallbackHint",
    "LearnerProfile",
    "Party",
    "Person",
    "Role",
    "RoleType",
    "TestCase",
    "Topic",
    "UserAccount",
]