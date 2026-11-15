import re

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .alerts import sync_signal_alert_events
from .auth import login_required
from .db import get_db
from .learning import FEATURED_LESSON, LEARN_CATEGORIES, LESSONS, get_lesson
from .models import AlertEvent, AlertRule, UserSettings
from .security import check_csrf

bp = Blueprint("pages", __name__)


@bp.route("/")
@login_required
def home():
    return render_template("home.html")


@bp.get("/learn")
@login_required
def learn():
    category = request.args.get("category", "all")
    valid_categories = {value for value, _label in LEARN_CATEGORIES}
    if category not in valid_categories:
        category = "all"
    lessons = (
        LESSONS
        if category == "all"
        else tuple(lesson for lesson in LESSONS if lesson["category"] == category)
    )
    return render_template(
        "learn/learn.html",
        categories=LEARN_CATEGORIES,
        selected_category=category,
        featured=FEATURED_LESSON,
        lessons=lessons,
    )


@bp.get("/learn/<slug>")
@login_required
def learn_lesson(slug):
    lesson = get_lesson(slug)
    if lesson is None:
        from flask import abort

        abort(404)
    return render_template("learn/lesson.html", lesson=lesson)


@bp.route("/alerts", methods=("GET", "POST"))
@login_required
def alerts():
    db = get_db()

    if request.method == "POST":
        check_csrf()
        action = request.form.get("action")
        if action in {"toggle", "delete", "read", "read_all"}:
            if action == "read_all":
                db.query(AlertEvent).filter(
                    AlertEvent.user_id == g.user.id,
                    AlertEvent.is_read.is_(False),
                ).update({"is_read": True}, synchronize_session=False)
                db.commit()
                return redirect(url_for("pages.alerts", filter="unread"))
            if action == "read":
                event = db.scalar(
                    select(AlertEvent).where(
                        AlertEvent.id == request.form.get("event_id"),
                        AlertEvent.user_id == g.user.id,
                    )
                )
                if event is not None:
                    event.is_read = True
                    db.commit()
                return redirect(url_for("pages.alerts"))
            rule = db.scalar(
                select(AlertRule).where(
                    AlertRule.id == request.form.get("rule_id"),
                    AlertRule.user_id == g.user.id,
                )
            )
            if rule is not None:
                if action == "delete":
                    db.query(AlertEvent).filter(
                        AlertEvent.rule_id == rule.id,
                    ).delete(synchronize_session=False)
                    db.delete(rule)
                else:
                    rule.enabled = not rule.enabled
                db.commit()
        else:
            ticker = request.form.get("ticker", "").strip().upper()
            condition = request.form.get("condition", "").strip()
            destination = request.form.get("destination", "app")
            errors = {}
            if not re.fullmatch(r"[A-Z0-9.-]{1,10}", ticker):
                errors["ticker"] = "Enter a valid ticker"
            if not condition:
                errors["condition"] = "Describe when to alert you"
            if destination not in {"app", "email"}:
                errors["destination"] = "Choose a destination"
            if errors:
                return render_alerts(db, errors=errors, form=request.form)
            db.add(
                AlertRule(
                    user_id=g.user.id,
                    ticker=ticker,
                    condition=condition,
                    destination=destination,
                )
            )
            db.commit()
            flash("Alert rule saved.", "success")
            sync_signal_alert_events(db)
        return redirect(url_for("pages.alerts"))

    return render_alerts(db)


def render_alerts(db, errors=None, form=None):
    sync_signal_alert_events(db)
    unread_only = request.args.get("filter") == "unread"
    event_query = select(AlertEvent).where(AlertEvent.user_id == g.user.id)
    if unread_only:
        event_query = event_query.where(AlertEvent.is_read.is_(False))
    alert_items = db.scalars(
        event_query.order_by(AlertEvent.created_at.desc()).limit(20)
    ).all()
    rules = db.scalars(
        select(AlertRule)
        .where(AlertRule.user_id == g.user.id)
        .order_by(AlertRule.id.desc())
    ).all()
    return render_template(
        "alerts/alerts.html",
        alert_items=alert_items,
        rules=rules,
        unread_only=unread_only,
        errors=errors or {},
        form=form or {},
    )


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
