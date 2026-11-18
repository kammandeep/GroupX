import re

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .alerts import sync_signal_alert_events
from .auth import login_required
from .db import get_db
from .learning import FEATURED_LESSON, LEARN_CATEGORIES, LESSONS, get_lesson
from .models import AlertEvent, AlertRule, Company, Stock, UserSettings
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
        abort(404)
    return render_template("learn/lesson.html", lesson=lesson)


@bp.route("/alerts", methods=("GET", "POST"))
@login_required
def alerts():
    db = get_db()

    if request.method == "POST":
        check_csrf()
        action = request.form.get("action")
        if action in {"toggle", "delete", "read", "read_all", "quick_add", "toggle_notifications"}:
            if action == "toggle_notifications":
                user_settings = db.scalar(
                    select(UserSettings).where(UserSettings.user_id == g.user.id)
                )
                if user_settings is None:
                    user_settings = UserSettings(user_id=g.user.id)
                    db.add(user_settings)
                    db.flush()
                user_settings.signal_alerts = not bool(user_settings.signal_alerts)
                db.commit()
                flash(
                    "App notifications enabled." if user_settings.signal_alerts
                    else "App notifications disabled.",
                    "success",
                )
                return redirect(url_for("pages.alerts"))
            if action == "quick_add":
                ticker = request.form.get("ticker", "").strip().upper()
                stock = db.scalar(
                    select(Stock).where(
                        Stock.ticker == ticker,
                        Stock.is_active.is_(True),
                    )
                )
                if stock is not None:
                    existing = db.scalar(
                        select(AlertRule).where(
                            AlertRule.user_id == g.user.id,
                            AlertRule.ticker == ticker,
                            AlertRule.destination == "app",
                        )
                    )
                    if existing is None:
                        db.add(AlertRule(
                            user_id=g.user.id,
                            ticker=ticker,
                            condition="Signal changes to BUY or SELL",
                            destination="app",
                            enabled=True,
                        ))
                        db.commit()
                        flash(f"{ticker} alert added.", "success")
                        sync_signal_alert_events(db)
                return redirect(url_for("pages.alerts"))
            if action == "read_all":
                db.query(AlertEvent).filter(
                    AlertEvent.user_id == g.user.id,
                    AlertEvent.is_read.is_(False),
                ).update({"is_read": True}, synchronize_session=False)
                db.commit()
                return redirect(url_for("pages.alerts", filter="read"))
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
            else:
                stock = db.scalar(
                    select(Stock).where(
                        Stock.ticker == ticker,
                        Stock.is_active.is_(True),
                    )
                )
                if stock is None:
                    errors["ticker"] = "Choose an active stock from the suggestions"
            if not condition:
                errors["condition"] = "Describe when to alert you"
            if destination not in {"app", "email"}:
                errors["destination"] = "Choose a destination"
            if errors:
                return render_alerts(db, errors=errors, form=request.form)
            existing = db.scalar(
                select(AlertRule).where(
                    AlertRule.user_id == g.user.id,
                    AlertRule.ticker == ticker,
                    AlertRule.destination == destination,
                )
            )
            if existing is not None:
                flash(f"{ticker} already has an alert.", "error")
                return redirect(url_for("pages.alerts"))
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
    filter_name = request.args.get("filter", "all")
    unread_only = filter_name == "unread"
    read_only = filter_name == "read"
    event_query = select(AlertEvent).where(AlertEvent.user_id == g.user.id)
    if unread_only:
        event_query = event_query.where(AlertEvent.is_read.is_(False))
    elif read_only:
        event_query = event_query.where(AlertEvent.is_read.is_(True))
    alert_items = db.scalars(
        event_query.order_by(AlertEvent.created_at.desc()).limit(20)
    ).all()
    rules = db.scalars(
        select(AlertRule)
        .where(AlertRule.user_id == g.user.id)
        .order_by(AlertRule.id.desc())
    ).all()
    popular_stocks = db.scalars(
        select(Stock)
        .where(Stock.is_active.is_(True))
        .order_by(Stock.ticker)
        .limit(4)
    ).all()
    user_settings = db.scalar(
        select(UserSettings).where(UserSettings.user_id == g.user.id)
    )
    app_notifications = user_settings.signal_alerts if user_settings is not None else True
    return render_template(
        "alerts/alerts.html",
        alert_items=alert_items,
        rules=rules,
        popular_stocks=popular_stocks,
        app_notifications=app_notifications,
        unread_only=unread_only,
        read_only=read_only,
        errors=errors or {},
        form=form or {},
    )


@bp.get("/api/alerts/status")
@login_required
def alert_status():
    db = get_db()
    sync_signal_alert_events(db)

    unread_count = db.scalar(
        select(func.count(AlertEvent.id))
        .join(AlertRule, AlertRule.id == AlertEvent.rule_id)
        .where(
            AlertEvent.user_id == g.user.id,
            AlertEvent.is_read.is_(False),
            AlertRule.destination == "app",
        )
    ) or 0

    items = db.scalars(
        select(AlertEvent)
        .join(AlertRule, AlertRule.id == AlertEvent.rule_id)
        .where(
            AlertEvent.user_id == g.user.id,
            AlertRule.destination == "app",
        )
        .order_by(AlertEvent.created_at.desc())
        .limit(10)
    ).all()

    return jsonify(
        unread_count=unread_count,
        alerts=[
            {
                "id": item.id,
                "title": item.title,
                "detail": item.detail,
                "tone": item.tone,
                "is_read": item.is_read,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
    )


@bp.get("/api/alerts/stocks")
@login_required
def alert_stock_search():
    db = get_db()
    query = request.args.get("q", "").strip().upper()
    if not query:
        return jsonify(stocks=[])

    statement = (
        select(Stock.ticker, Company.name)
        .join(Company, Company.id == Stock.company_id)
        .where(
            Stock.is_active.is_(True),
            (Stock.ticker.contains(query)) | (Company.name.ilike(f"%{query}%")),
        )
        .order_by(
            (Stock.ticker != query),
            Stock.ticker,
        )
        .limit(8)
    )
    rows = db.execute(statement).all()
    return jsonify(
        stocks=[
            {"ticker": ticker, "name": company_name}
            for ticker, company_name in rows
        ]
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
