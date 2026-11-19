import functools
import re
from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .db import get_db
from .models import User
from .security import check_csrf

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
# Used so a login for an unknown email takes as long as a real one.
DUMMY_HASH = generate_password_hash("not-a-real-password")


@bp.before_app_request
def load_logged_in_user():
    """Runs before every request: put the current user (or None) on g.user."""
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = get_db().get(User, user_id)
        if g.user is None: # account was deleted: drop the stale session
            session.clear()


def login_required(view):
    """Decorator for any page that needs a signed-in user."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


@bp.route("/signup", methods=("GET", "POST"))
def signup():
    if g.user:
        return redirect(url_for("pages.home"))

    username = email = ""
    errors = {}
    status = 200

    if request.method == "POST":
        check_csrf()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not USERNAME_RE.match(username):
            errors["username"] = "Use 3 to 20 letters, numbers or underscores"
        if not EMAIL_RE.match(email):
            errors["email"] = "Enter a valid email"
        if len(password) < 8:
            errors["password"] = "Use at least 8 characters"

        if errors:
            status = 400
        else:
            db = get_db()
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
            )
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                errors["form"] = "An account with that email or username already exists"
                status = 409
            else:
                session.clear()
                session["user_id"] = user.id
                return redirect(url_for("onboarding.onboarding"))  # new accounts answer the questions first

    return render_template("auth/signup.html", username=username, email=email, errors=errors), status


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("pages.home"))

    email = ""
    errors = {}
    status = 200

    if request.method == "POST":
        check_csrf()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.scalar(select(User).where(User.email == email))
        hash_to_check = user.password_hash if user else DUMMY_HASH
        valid = check_password_hash(hash_to_check, password)

        if user is None or not user.is_active or not valid:
            errors["form"] = "Incorrect email or password"  # same message for both cases
            status = 401
        else:
            user.last_login_at = datetime.now()
            db.commit()
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("pages.home"))  # home sends unfinished users to onboarding

    return render_template("auth/login.html", email=email, errors=errors), status


@bp.post("/logout")
def logout():
    check_csrf()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
