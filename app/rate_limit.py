"""
Rate limiting (spec PR-N3): caps how often one client can repeat an
expensive or sensitive action. Over the limit, the client gets 429 Too Many
Requests with a Retry-After header.

Only actions are limited (POST and PUT), never viewing pages. Visitors are
counted by IP address and signed-in users by their account, so people
sharing one network are counted separately once they log in.

Counts are kept in memory, one store per app instance. That keeps each
test's app separate, and needs nothing extra to run. The trade-off: counts
reset when the server restarts and are not shared between several server
processes. PyQuest runs one process on its free hosting, so this is
sufficient; a shared store (such as Redis) would be the next step at scale.
"""

import threading
import time
from functools import wraps

from flask import current_app, jsonify, request
from flask_login import current_user

# name: (requests allowed, per this many seconds). Tunable.
LIMITS = {
    "login": (10, 60),
    "register": (5, 3600),
    "guest": (5, 3600),
    "hint": (30, 60),
    "explanation": (30, 60),
    "chat": (20, 60),
    "review": (10, 60),
    "submission": (60, 60),
    "code-save": (120, 60),
}

LIMITED_METHODS = ("POST", "PUT")
TOO_MANY_MESSAGE = "Too many requests. Please wait a moment and try again."

# Expired counters are cleared out once the store holds this many, so
# memory use stays bounded.
_CLEANUP_THRESHOLD = 10_000


def clock():
    """The current time in seconds. A function so tests can replace it."""
    return time.monotonic()


class _Store:
    """Fixed-window counters: each key counts requests in its current window."""

    def __init__(self):
        self._lock = threading.Lock()
        self._windows = {}

    def hit(self, key, limit, period, now):
        """Count one request. Returns (allowed, seconds until the window resets)."""
        with self._lock:
            if len(self._windows) > _CLEANUP_THRESHOLD:
                self._windows = {
                    k: (start, count, p)
                    for k, (start, count, p) in self._windows.items()
                    if now - start < p
                }

            start, count, _ = self._windows.get(key, (now, 0, period))
            if now - start >= period:
                start, count = now, 0
            count += 1
            self._windows[key] = (start, count, period)
            return count <= limit, max(1, int(start + period - now))


def _store():
    return current_app.extensions.setdefault("pyquest_rate_limits", _Store())


def _client_key():
    if current_user.is_authenticated:
        return f"user:{current_user.id}"
    return f"ip:{request.remote_addr}"


def _too_many(retry_after):
    if request.path.startswith("/api/"):
        response = jsonify(error=TOO_MANY_MESSAGE)
        response.status_code = 429
    else:
        response = current_app.response_class(TOO_MANY_MESSAGE, status=429, mimetype="text/plain")
    response.headers["Retry-After"] = str(retry_after)
    return response


def rate_limit(name):
    """Limit a view's POST and PUT requests by the rule called name in LIMITS.

    Place it below any login or role check, so requests that are refused
    anyway do not use up the allowance.
    """
    limit, period = LIMITS[name]

    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if request.method in LIMITED_METHODS and current_app.config.get(
                "RATE_LIMITS_ENABLED", True
            ):
                allowed, retry_after = _store().hit(
                    f"{name}:{_client_key()}", limit, period, clock()
                )
                if not allowed:
                    return _too_many(retry_after)
            return view(*args, **kwargs)

        return wrapped_view

    return decorator