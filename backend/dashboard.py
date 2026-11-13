from flask import render_template, Blueprint, g, redirect, url_for
from sqlalchemy import select, func
from . import db
from datetime import date
from .models import ( Company, Stock, StockData, Prediction, UserWatchlist, WatchlistItem, TradingSignal)

bp = Blueprint('dashboard', __name__)

@bp.route('/dashboard')
def dashboard():
    
    if g.user is None:
        return redirect(url_for('auth.login'))
    
    session = db.get_db()
    
    active_strat = session.scalar(
        select(func.count(func.distinct(TradingSignal.model_name)))
    ) or 0
    
    signals_today = session.scalar(
        select(func.count()).select_from(TradingSignal).where(func.date(TradingSignal.signal_timestamp) == date.today().isoformat())
    ) or 0
    
    backtest = db.execute(
        "SELECT AVG(accuracy) FROM backtests"
    ).fetchone()[0]
    
    held = session.execute(
        select(WatchlistItem.ticker, Company.name).join(UserWatchlist, UserWatchlist.id == WatchlistItem.watchlist_id).join(Stock, Stock.ticker == WatchlistItem.ticker).join(Company, Company.id == Stock.company_id).where(UserWatchlist.user_id == g.user.id).distinct()
    ).all()
    
    watchlist = db.execute(
                "SELECT symbol, name, signal AS signal_type, close AS price, change_pct, best_strategy FROM watchlist WHERE status = 'active'"
            ).fetchall()
    
    signals = db.execute(
        "SELECT symbol, company_name, accuracy, signal_type "
        "FROM signals WHERE date(created_at) = date('now')"
        "ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    
    rows = db.execute(
        "SELECT date, actual, predicted FROM results ORDER BY date"
    ).fetchall()
    
    chart_label = [r["date"] for r in rows]
    chart_actual = [r["actual"] for r in rows]
    chart_pred = [r["predicted"] for r in rows]
    
    return render_template(
        'dashboard.html',
        active_strat=active_strat,
        signals_today=signals_today,
        backtest=backtest,
        watchlist=watchlist,
        watchlist_count=watchlist_count,
        signals=signals,
        rows=rows
        )