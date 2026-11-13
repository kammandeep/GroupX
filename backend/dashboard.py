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
    
    watchlists = []
    
    for ticker, name in held:
        closes = session.scalars(
            select(StockData.close).where(StockData.ticker == ticker).order_by(StockData.date.desc()).limit(2)
        ).all()
        price = closes[0] if closes else 0
        change_pct = ((closes[0]-closes[1]) / closes[1] * 100 if len(closes) == 2 and closes[1] else 0)
        sig = session.execute(
            select(TradingSignal.signal_type, TradingSignal.model_name).where(TradingSignal.ticker == ticker).order_by(TradingSignal.signal_timestamp.desc()).limit(1)
        ).first()
        watchlists.append({
            "symbol":ticker,
            "name": name,
            "price":price,
            "change_pct":change_pct,
            "best_strategy":sig.model_name if sig else "n/a",
            "signal_type":sig.signal_type if sig else "HOLD",
        })
        
    watchlist_count = len(watchlists)
    
    sig_rows = session.execute(
        select(TradingSignal, Company.name).join(Stock, Stock.ticker == TradingSignal.ticker).join(Company, Company.id == Stock.company_id).order_by(TradingSignal.signal_timestamp.desc()).limit(5)
    ).all()
    
    signals = session.execute(
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