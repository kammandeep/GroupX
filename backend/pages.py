import re

from flask import Blueprint, flash, g, render_template, request, url_for, redirect
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .auth import login_required
from .db import get_db
from .models import UserSettings
from .security import check_csrf
from .onboarding import onboarding_required


bp = Blueprint("pages", __name__)


@bp.route("/")
@login_required
@onboarding_required
def home():
    if g.user:
        return redirect(url_for("dashboard.dashboard"))

    return redirect(url_for("auth.login"))


@bp.route("/settings", methods=("GET", "POST"))
@login_required
def settings():
    db = get_db()
    user_settings = db.scalar(
        select(UserSettings).where(UserSettings.user_id == g.user.id)
    )
    if user_settings is None:
        user_settings = UserSettings(user_id=g.user.id)
        db.add(user_settings)
        db.commit()

    errors = {}
    saved = False

    if request.method == "POST":
        check_csrf()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        experience_level = request.form.get("experience_level", "")
        risk_comfort = request.form.get("risk_comfort", "")

        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
            errors["username"] = "Use 3 to 20 letters, numbers or underscores"
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors["email"] = "Enter a valid email"
        if experience_level not in {"beginner", "intermediate", "pro"}:
            errors["experience_level"] = "Choose an experience level"
        if risk_comfort not in {"low", "medium", "high"}:
            errors["risk_comfort"] = "Choose a risk comfort level"

        if not errors:
            g.user.username = username
            g.user.email = email
            user_settings.experience_level = experience_level
            user_settings.risk_comfort = risk_comfort
            user_settings.signal_alerts = "signal_alerts" in request.form
            user_settings.daily_summary = "daily_summary" in request.form
            user_settings.strategy_updates = "strategy_updates" in request.form
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                errors["form"] = "That username or email is already in use"
            else:
                saved = True
                flash("Your settings have been saved.", "success")

    return render_template(
        "settings/settings.html",
        settings=user_settings,
        errors=errors,
        saved=saved,
    )
