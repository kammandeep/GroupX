from flask import Flask, render_template, Blueprint

bp = Blueprint('dashboard', __name__)

def dashboard():
    db = get_db()
    
    active_strat = db.execute(
        "SELECT COUNT(*) FROM strategies WHERE status = 'active'"
    ).fetchone()[0]
    
    signals_today = db.execute(
        "SELECT COUNT(*) FROM signals WHERE date(created_at) = date('now')"
    ).fetchone()[0]
    
    backtest = db.execute(
        "SELECT AVG(accuracy) FROM backtests"
    )
    
    watchlist = db.execute(
        "SELECT COUNT(*) FROM symbol WHERE status = 'active'"
    )
    
    return render_template(
        'dashboard.html',
        active_strat=active_strat,
        signals_today=signals_today,
        backtest=backtest,
        watchlist=watchlist
    )