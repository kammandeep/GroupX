from flask import render_template, Blueprint, g, redirect, url_for
from sqlalchemy import select, func
from . import db
from datetime import date
from .models import ( Company, Stock, StockData, Prediction, UserWatchlist, WatchlistItem, TradingSignal)

bp = Blueprint('watchlist', __name__)

@bp.route('/watchlist')
def watchlist():
    
    if g.user is None:
        return redirect(url_for('auth.login'))
    
    session = db.get_db()
    
    watchlist = db.execute(
            "SELECT symbol, name, signal AS signal_type, close AS price, change_pct, best_strategy FROM watchlist WHERE status = 'active'"
        ).fetchall()
    
    return render_template(
            'watchlist.html',
            watchlist=watchlist
        )