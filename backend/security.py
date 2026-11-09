import secrets
from flask import abort, request, session


def csrf_token():
    """Return this session's CSRF token, creating it on first use."""
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def check_csrf():
    """Call at the top of every POST handler."""
    sent = request.form.get("csrf_token", "")
    expected = session.get("_csrf", "")
    if not sent or not expected or not secrets.compare_digest(sent, expected):
        abort(400)