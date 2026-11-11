from flask import Flask, render_template, Blueprint

bp = Blueprint('dashboard', __name__)

def dashboard():
    db = get_db() #replace with actual database get function
    
    active_strat = db.execute(
        "SELECT COUNT(*) FROM strategies WHERE status = 'active'"
    ).fetchone()[0]
    
    signals_today = db.execute(
        "SELECT COUNT(*) FROM signals WHERE date(created_at) = date('now')"
    ).fetchone()[0]
    
    backtest = db.execute(
        "SELECT AVG(accuracy) FROM backtests"
    ).fetchone()[0]
    
    watchlist = db.execute(
        "SELECT COUNT(*) FROM symbol WHERE status = 'active'"
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
        signals=signals,
        rows=rows
    )