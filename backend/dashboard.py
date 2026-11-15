from flask import render_template, Blueprint, g, redirect, url_for
from sqlalchemy import select, func
from . import db
from datetime import date
from .models import ( Company, Stock, StockData, Prediction, UserWatchlist, WatchlistItem, TradingSignal)
from .auth import login_required

bp = Blueprint('dashboard', __name__)

@bp.route('/dashboard')
@login_required
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
    
    avg_err = session.scalar(
        select(func.avg(
            func.abs(Prediction.predicted_close - Prediction.actual_close) / Prediction.actual_close
        )).where(Prediction.actual_close.is_not(None))
    )
    
    backtest = round((1 - avg_err) * 100, 1) if avg_err is not None else 0
    
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
    
    signals = [
        {
        "symbol":s.ticker,
        "name":company_name,
        "accuracy": (s.confidence_score or 0)*100,
        "signal_type": s.signal_type,
        }
        for s, company_name in sig_rows
    ]
    
    #======================================
    # CHART SECTION
    #======================================
    
    chart_ticker = (watchlists[0]["symbol"] if watchlists else session.scalar(select(Prediction.ticker).limit(1)))
    preds = session.scalars(
        select(Prediction).where(Prediction.ticker == chart_ticker, Prediction.actual_close.is_not(None)).order_by(Prediction.prediction_date)
    ).all()
    

    
    return render_template(
        'dashboard.html',
        active_strat=active_strat,
        signals_today=signals_today,
        backtest=backtest,
        watchlists=watchlists,
        watchlist_count=watchlist_count,
        signals=signals,
        chart_labels = [p.prediction_date for p in preds],
        chart_actual = [p.actual_close for p in preds],
        chart_predicted = [p.predicted_close for p in preds]
        )