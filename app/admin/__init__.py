"""
Admin blueprint: managing users, roles, and account status (spec FR13),
with every change recorded in the audit log (PR-M1).

Every route requires the system administrator role. The rules themselves
(and their safeguards) live in app/services/admin.py, so they apply however
a request arrives.
"""

from flask import Blueprint

# url_prefix puts every route in this blueprint under /admin.
bp = Blueprint("admin", __name__, url_prefix="/admin")

# Imported at the bottom on purpose: routes.py attaches its views to `bp`,
# so `bp` must exist first.
from app.admin import routes  # noqa: E402, F401