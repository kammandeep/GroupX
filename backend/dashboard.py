from flask import render_template, Blueprint, g
from sqlalchemy import select, func
from . import db, queries
from .auth import login_required
from .models import Prediction, Strategy

bp = Blueprint('dashboard', __name__)

@bp.route('/dashboard')
@login_required
def dashboard():
    
    session = db.get_db()
    
    active_strat = session.scalar(
        select(func.count()).select_from(Strategy).where(Strategy.is_active.is_(True))) or 0
    
    todays = queries.latest_signals(session)
    
    avg_err = session.scalar(
        select(func.avg(
            func.abs(Prediction.predicted_close - Prediction.actual_close) / Prediction.actual_close
        )).where(Prediction.actual_close.is_not(None))
    )
    
    backtest = round((1 - avg_err) * 100, 1) if avg_err is not None else 0
    
    watchlists = []
    for row in queries.watchlist_overview(session, g.user.id):
        best = max(row["signals"], key=lambda s: s["confidence"], default=None)
        watchlists.append({
            "symbol" : row["ticker"],
            "name" : row["company_name"],
            "price" : row["close"],
            "change_pct" : row["change_pct"] or 0,
            "best_strategy" : best["strategy"] if best else "n/a",
            "signal_type" : best["signal"] if best else "HOLD",
        })
    
    top = sorted(todays, key=lambda s: s["confidence"], reverse=True) [:5]
    
    signals = [
        {
        "symbol" : s["ticker"],
        "name" : s["company_name"],
        "accuracy": s["confidence"] * 100,
        "signal_type": s["signal"],
        }
        for s in top
    ]
    
    #======================================
    # CHART SECTION
    #======================================
    
    chart_ticker = watchlists[0]["symbol"] if watchlists else session.scalar(
        select(Prediction.ticker).where(Prediction.actual_close.is_not(None)).limit(1))
    chart_model = session.scalar(
        select(Prediction.model_name).where(Prediction.ticker == chart_ticker, Prediction.actual_close.is_not(None)).limit(1))
    preds = session.scalars(
        select(Prediction).where(Prediction.ticker == chart_ticker, Prediction.model_name == chart_model, Prediction.actual_close.is_not(None)).order_by(Prediction.prediction_date)).all()
    
    
    return render_template(
        'dashboard.html',
        active_strat=active_strat,
        signals_today=len(todays),
        backtest=backtest,
        watchlists=watchlists,
        watchlist_count=len(watchlists),
        signals=signals,
        chart_labels = [p.prediction_date for p in preds],
        chart_actual = [p.actual_close for p in preds],
        chart_predicted = [p.predicted_close for p in preds],
        )