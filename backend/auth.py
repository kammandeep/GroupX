import re
from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from db import engine
from models import User

bp = Blueprint("auth", __name__)

# Make sure the users table exists (does nothing if it is already there).
User.__table__.create(bind=engine, checkfirst=True)

# Checked when an email is not found, so unknown emails and wrong passwords take the same time.
DUMMY_HASH = generate_password_hash("not-a-real-password")


@bp.before_app_request
def load_user():
    """Runs before every request: g.user is the logged-in user, or None."""
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        with Session(engine) as db:
            user = db.get(User, user_id)
            if user and user.is_active:
                g.user = {"id": user.id, "username": user.username, "email": user.email}


def login_required(view):
    """Put @auth.login_required under @app.route to protect a page."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


@bp.after_app_request
def no_cache(response):
    """Stops the Back button from showing a protected page after logging out."""
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("index"))

    username, email, errors = "", "", {}

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # 1. validate
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
            errors["username"] = "Use 3 to 20 letters, numbers or underscores"
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors["email"] = "Enter a valid email"
        if len(password) < 8:
            errors["password"] = "Use at least 8 characters"

        # 2. save to the users table (password stored as a hash, never as text)
        if not errors:
            with Session(engine) as db:
                taken = db.scalar(select(User.id).where(
                    or_(func.lower(User.username) == username.lower(), User.email == email)))
                if taken:
                    errors["form"] = "An account with that email or username already exists"
                else:
                    now = datetime.now()
                    user = User(username=username, email=email,
                                password_hash=generate_password_hash(password),
                                created_at=now, updated_at=now, is_active=1)
                    db.add(user)
                    try:
                        db.commit()
                    except IntegrityError:          # two people signed up at the same moment
                        db.rollback()
                        errors["form"] = "An account with that email or username already exists"
                    else:
                        session.clear()
                        session["user_id"] = user.id        # log them in straight away
                        return redirect(url_for("index"))

    return render_template("auth/signup.html", username=username, email=email, errors=errors)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))

    email, errors = "", {}

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with Session(engine) as db:
            user = db.scalar(select(User).where(User.email == email))
            hash_to_check = user.password_hash if user else DUMMY_HASH
            valid = check_password_hash(hash_to_check, password)

            # same message for "no such email" and "wrong password"
            if user is None or not valid or not user.is_active:
                errors["form"] = "Incorrect email or password"
            else:
                session.clear()
                session["user_id"] = user.id
                return redirect(url_for("index"))

    return render_template("auth/login.html", email=email, errors=errors)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("auth.login"))
