from flask import render_template, Blueprint, g, request, redirect, url_for, flash
from sqlalchemy import select

from . import db, queries
from .auth import login_required
from .models import Stock, UserWatchlist, WatchlistItem
from .security import check_csrf


bp = Blueprint('watchlist', __name__)


"""Add a stock to the users lists, creates the list for the first time and should be safe to call twice"""
def add_to_watchlist(session, user_id, ticker, list_name="My watchlist"):
    stock = session.scalar(select(Stock).where(Stock.ticker == ticker.upper(), Stock.is_active.is_(True)))
    if stock is None:
        raise ValueError(f"{ticker} is not a tracked NASDAQ stock")

    watchlist = session.scalar(select(UserWatchlist).where(
        UserWatchlist.user_id == user_id, UserWatchlist.name == list_name))
    if watchlist is None:
        watchlist = UserWatchlist(user_id=user_id, name=list_name)
        session.add(watchlist)
        session.flush()

    exists = session.scalar(select(WatchlistItem.id).where(
        WatchlistItem.watchlist_id == watchlist.id, WatchlistItem.ticker == stock.ticker))
    if exists is None:
        session.add(WatchlistItem(watchlist_id=watchlist.id, ticker=stock.ticker))
    session.commit()

@bp.post('/watchlist/add')
@login_required
def add():
    check_csrf()
    ticker = request.form.get("ticker", "").strip().upper()
    try:
        add_to_watchlist(db.get_db(), g.user.id, ticker)
    except ValueError as e:
        flash(str(e), "error")
    else:
        flash(f"{ticker} added to your watchlist", "info")
    return redirect(url_for("watchlist.watchlist"))

@bp.route('/watchlist')
@login_required
def watchlist():  
    session = db.get_db()
    rows = queries.watchlist_overview(session, g.user.id)
    watched = set(queries.watchlist_tickers(session, g.user.id))
    available = [t for t in session.scalars(
        select(Stock.ticker).where(Stock.is_active.is_(True)).order_by(Stock.ticker))
        if t not in watched]
    return render_template(
            'watchlist/watchlist.html',
            watchlist=rows,
            available=available
        )
    
