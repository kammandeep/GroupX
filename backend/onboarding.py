import functools
from datetime import datetime

from flask import Blueprint, abort, g, redirect, render_template, request, url_for
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from .auth import login_required
from .db import get_db
from .models import Company, Stock, UserProfile, UserWatchlist, WatchlistItem
from .security import check_csrf

bp = Blueprint("onboarding", __name__)

WATCHLIST_NAME = "My watchlist"

# kind "choice": pick one card, saved in the UserProfile column named by `key`.
# kind "stocks": pick any number of stocks, saved to the user's watchlist. Keep it as the last step.
# To change a question, edit this list. To remove a step, delete its entry (the progress bar adjusts itself).
STEPS = (
    {
        "kind": "choice",
        "key": "goal",
        "title": "What do you want from JAK?",
        "subtitle": "Pick the one that fits best. You can change it later.",
        "hint": "Next: tell us how much trading experience you have.",
        "options": (
            {"value": "learn", "title": "Learn", "text": "Show me how trading signals work", "tag": ""},
            {"value": "compare", "title": "Compare", "text": "Help me compare strategies", "tag": ""},
            {"value": "ideas", "title": "Find ideas", "text": "Point me to stocks worth researching", "tag": ""},
        ),
    },
    {
        "kind": "choice",
        "key": "experience_level",
        "title": "How much trading experience do you have?",
        "subtitle": "We use this to set how much guidance you see. You can change it later.",
        "hint": "Next: pick the stocks you want to follow.",
        "options": (
            {"value": "beginner", "title": "Just starting", "text": "I want plain-English help", "tag": "Beginner mode"},
            {"value": "some", "title": "Some experience", "text": "I know the basics", "tag": "Light tips"},
            {"value": "experienced", "title": "Experienced", "text": "I only need the data", "tag": "No tips"},
        ),
    },
    {
        "kind": "stocks",
        "title": "Which stocks do you want to follow?",
        "subtitle": "They go on your watchlist. Pick as many as you like, or skip this for now.",
        "hint": "That's the last step. You can change all of this later.",
    },
)


# where is this user up to? 

def get_profile(user_id):
    return get_db().get(UserProfile, user_id)


def step_is_done(item, profile):
    if item["kind"] == "choice":
        return getattr(profile, item["key"]) is not None
    return profile.completed_at is not None


def current_step(profile):
    """Number (starting at 1) of the first unfinished step, or None when onboarding is complete."""
    if profile is not None and profile.completed_at is not None:
        return None
    for number, item in enumerate(STEPS, start=1):
        if profile is None or not step_is_done(item, profile):
            return number
    return len(STEPS)


def onboarding_required(view):
    """Put under @login_required on any page that needs onboarding finished first."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_step(get_profile(g.user.id)) is not None:
            return redirect(url_for("onboarding.onboarding"))
        return view(*args, **kwargs)
    return wrapped


# saving

def available_stocks():
    """The stocks a user can follow: (ticker, company name), only active ones."""
    return get_db().execute(
        select(Stock.ticker, Company.name)
        .join(Company, Company.id == Stock.company_id)
        .where(Stock.is_active.is_(True))
        .order_by(Stock.ticker)
    ).all()


def follow_stocks(user_id, tickers):
    """Make the user's watchlist hold exactly these tickers (safe to run again)."""
    db = get_db()
    watchlist = db.scalar(select(UserWatchlist).where(
        UserWatchlist.user_id == user_id, UserWatchlist.name == WATCHLIST_NAME))
    if watchlist is None:
        watchlist = UserWatchlist(user_id=user_id, name=WATCHLIST_NAME)
        db.add(watchlist)
        db.flush()

    already = set(db.scalars(select(WatchlistItem.ticker).where(WatchlistItem.watchlist_id == watchlist.id)))
    db.execute(delete(WatchlistItem).where(
        WatchlistItem.watchlist_id == watchlist.id, WatchlistItem.ticker.not_in(tickers)))
    for ticker in tickers - already:
        db.add(WatchlistItem(watchlist_id=watchlist.id, ticker=ticker))


def followed_tickers(user_id):
    return set(get_db().scalars(
        select(WatchlistItem.ticker)
        .join(UserWatchlist, UserWatchlist.id == WatchlistItem.watchlist_id)
        .where(UserWatchlist.user_id == user_id, UserWatchlist.name == WATCHLIST_NAME)))


# pages

@bp.route("/onboarding")
@login_required
def onboarding():
    """Send the user to the step they are up to (or home if they are finished)."""
    number = current_step(get_profile(g.user.id))
    if number is None:
        return redirect(url_for("pages.home"))
    return redirect(url_for("onboarding.step", number=number))


@bp.route("/onboarding/<int:number>", methods=("GET", "POST"))
@login_required
def step(number):
    profile = get_profile(g.user.id)
    furthest = current_step(profile)
    if furthest is None:
        return redirect(url_for("pages.home"))
    if not 1 <= number <= len(STEPS):
        abort(404)
    if number > furthest:  # no skipping ahead
        return redirect(url_for("onboarding.step", number=furthest))

    current = STEPS[number - 1]
    stocks = available_stocks() if current["kind"] == "stocks" else []
    # What to show as picked: what they chose before, otherwise the first card
    if current["kind"] == "choice":
        picked = getattr(profile, current["key"], None) if profile else None
        picked = picked or current["options"][0]["value"]
    else:
        picked = followed_tickers(g.user.id)
    error = None
    status = 200

    if request.method == "POST":
        check_csrf()
        if current["kind"] == "choice":
            picked = request.form.get(current["key"], "")
            valid = picked in {option["value"] for option in current["options"]}
        else:
            picked = set(request.form.getlist("tickers"))
            valid = picked <= {ticker for ticker, _name in stocks}  # only stocks we showed

        if not valid:
            error = "Choose one of the options shown"
            status = 400
        else:
            if profile is None:
                profile = UserProfile(user_id=g.user.id)
                get_db().add(profile)
            if current["kind"] == "choice":
                setattr(profile, current["key"], picked)
            else:
                follow_stocks(g.user.id, picked)
            if number == len(STEPS):
                profile.completed_at = datetime.now()
            try:
                get_db().commit()
            except IntegrityError:
                get_db().rollback()  # double-click: the other request already saved this step
            return redirect(url_for("onboarding.onboarding"))

    return render_template("onboarding.html", step=current, number=number, total=len(STEPS),
                           picked=picked, stocks=stocks, error=error), status