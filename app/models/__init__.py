"""
Database models for PyQuest.

Every model is imported here so that importing this one package registers
all tables with SQLAlchemy. The application factory imports it, which is
what lets Flask-Migrate detect schema changes and lets tests create every
table with db.create_all().

Models are split into modules by feature area (identity now; challenges,
submissions, and the AI Coach later), matching the blueprint structure.
"""

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
    "LearnerProfile",
    "Party",
    "Person",
    "Role",
    "RoleType",
    "UserAccount",
]