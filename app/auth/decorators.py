"""
Access control decorators (spec FR03).

A decorator is placed above a view to add behaviour before it runs:

    @bp.route("/dashboard")
    @role_required(RoleType.LEARNER)
    def dashboard():
        ...

Every protected route declares its allowed roles this way, and the check
runs on the server for every request. Hiding a link in the page is never
the only protection, because anyone can type a URL directly.
"""

from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def role_required(*role_types):
    """Allow a view only for signed-in users holding at least one of the roles.

    - Not signed in: redirected to the login page (via login_required), which
      returns them here after a successful login.
    - Signed in without any of the roles: 403 Forbidden.

    Args:
        role_types: one or more RoleType values; holding any one is enough.
    """

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped_view(*args, **kwargs):
            if not any(current_user.has_role(role) for role in role_types):
                abort(403)
            return view(*args, **kwargs)

        return wrapped_view

    return decorator