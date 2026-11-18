"""This page is for database queriees, pages, and api share. Routes call these so no other route needs its own SQL"""

"""This file only reads, the ML pipelines writes prices, predictions and signals, the web app writes users and watchlists in the auth.py and the watchlist routes"""

from sqlalchemy import func, select

from .models import (
    Company,
    Prediction,
    Stock,
    StockData,
    Strategy,
    TradingSignal,
    UserWatchlist,
    WatchlistItem,
)

"""Latest close, previous day's close and the move between them, for each active stock, returns a list of dicts that is sorted by tickers"""
def latest_prices(session, tickers=None):
    ranked = select(
        StockData.ticker,
        StockData.date,
        StockData.close,
        func.lag(StockData.close).over(partition_by=StockData.ticker, order_by=StockData.date).label("prev_close"),
        func.row_number().over(partition_by=StockData.ticker, order_by=StockData.date.desc()).label("rn"),
    ).subquery()

    query = (
        select(Stock.ticker, Company.name, Stock.exchange_code, ranked.c.date, ranked.c.close, ranked.c.prev_close)
        .join(Company, Company.id == Stock.company_id)
        .join(ranked, ranked.c.ticker == Stock.ticker)
        .where(ranked.c.rn == 1, Stock.is_active.is_(True))
        .order_by(Stock.ticker)
    )
    if tickers is not None:
        query = query.where(Stock.ticker.in_(tickers))

    rows = []
    for ticker, name, exchange, date, close, prev_close in session.execute(query):
        change = None if prev_close is None else round(close - prev_close, 2)
        change_pct = None if not prev_close else round(change / prev_close * 100, 2)
        rows.append({
            "ticker": ticker, "company_name": name, "exchange": exchange, "date": date,
            "close": close, "prev_close": prev_close, "change": change, "change_pct": change_pct,
            "movement": "flat" if not change else ("up" if change > 0 else "down"),
        })
    return rows

"""return the close history for each of the companies currently stored over the last 30 days"""
def price_history(session, tickers, days=30):
    ranked = select(
        StockData.ticker, StockData.date, StockData.close, 
        func.row_number().over(partition_by=StockData.ticker, order_by=StockData.date.desc()).label("rn"),
    ).where(StockData.ticker.in_(tickers)).subquery()
    rows = session.execute(
        select(ranked.c.ticker, ranked.c.close).where(ranked.c.rn <= days).order_by(ranked.c.ticker, ranked.c.date)
    )
    history = {}
    for ticker, close in rows:
        history.setdefault(ticker, []).append(close)
    return history
    
"""The newest day of signals, one row per stock per strategy, so the UI can show
    which strategy says BUY, SELL or HOLD for each stock."""
def latest_signals(session, ticker=None, strategy_id=None):

    newest_day = select(func.max(TradingSignal.signal_date)).scalar_subquery()
    query = (
        select(TradingSignal, Strategy.name, Company.name)
        .join(Strategy, Strategy.id == TradingSignal.strategy_id)
        .join(Stock, Stock.ticker == TradingSignal.ticker)
        .join(Company, Company.id == Stock.company_id)
        .where(TradingSignal.signal_date == newest_day, Strategy.is_active.is_(True))
        .order_by(TradingSignal.ticker, Strategy.name)
    )
    if ticker:
        query = query.where(TradingSignal.ticker == ticker)
    if strategy_id:
        query = query.where(TradingSignal.strategy_id == strategy_id)

    return [
        {
            "ticker": s.ticker, "company_name":company_name, "strategy": strategy_name, "signal": s.signal_type,
            "confidence": s.confidence_score, "target_price": s.target_price, "date": s.signal_date,
        }
        for s, strategy_name, company_name in session.execute(query)
    ]

"""Newest forecast from each model for one stock."""
def latest_predictions(session, ticker): 
    newest = (
        select(Prediction.model_name, func.max(Prediction.prediction_date).label("d"))
        .where(Prediction.ticker == ticker).group_by(Prediction.model_name).subquery()
    )
    query = select(Prediction).join(
        newest, (Prediction.model_name == newest.c.model_name) & (Prediction.prediction_date == newest.c.d)
    ).where(Prediction.ticker == ticker)
    return [
        {"model": p.model_name, "date": p.prediction_date, "predicted_close": p.predicted_close,
         "direction": p.direction, "confidence": p.confidence_score}
        for p in session.scalars(query)
    ]


"""Every ticker on any of this user's watchlists."""
def watchlist_tickers(session, user_id):
    return session.scalars(
        select(WatchlistItem.ticker)
        .join(UserWatchlist, UserWatchlist.id == WatchlistItem.watchlist_id)
        .where(UserWatchlist.user_id == user_id)
        .distinct()
    ).all()


"""The user's watched stocks with prices and today's signals together: one page, one call."""
def watchlist_overview(session, user_id):
    tickers = watchlist_tickers(session, user_id)
    if not tickers:
        return []
    signals_by_ticker = {}
    for s in latest_signals(session):
        signals_by_ticker.setdefault(s["ticker"], []).append(s)
    history = price_history(session, tickers)
    
    result = []
    
    for row in latest_prices(session, tickers):
        sigs = signals_by_ticker.get(row['ticker'], [])
        best = max(sigs, key=lambda s: s['confidence'] or 0) if sigs else None
        result.append({
            **row,
            "symbol" : row['ticker'],
            "name" : row['company_name'],
            "price" : row['close'],
            "history" : history.get(row['ticker'], []),
            "signal_type" : best['signal'] if best else None,
            "best_strategy" : best['strategy'].replace("Live ", "").replace("_", " ") if best else None,
            "signals" : sigs,
        })
    
    return result



