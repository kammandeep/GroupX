"""Stock detail page: price chart, today's signal and every strategy's view of one stock."""

from flask import Blueprint, abort, g, render_template, request

from . import db, queries
from .auth import login_required
from .charts import build_chart
from .strategies import analyse
from .strategy_rules import BACKTEST_DAYS, STRATEGIES, WARMUP, adjust_for_splits, period_label

bp = Blueprint("stocks", __name__)

# Trading days shown for each range pill; None means everything we have.
RANGES = {"1M": 21, "6M": 126, "1Y": 252, "5Y": None}
DEFAULT_RANGE = "1Y"


@bp.get("/stocks/<ticker>")
@login_required
def stock_detail(ticker):
    session = db.get_db()
    ticker = ticker.upper()
    stock = queries.close_series(session, BACKTEST_DAYS + WARMUP).get(ticker)
    if stock is None:
        abort(404)

    rows = []
    for strategy in STRATEGIES:
        found = analyse(strategy, {ticker: stock})  # empty when there is too little history
        if found:
            rows.append({"strategy": strategy, **found[0]})
    if not rows:
        return render_template("stocks/detail.html", ticker=ticker, stock=stock, rows=[], best=None)

    best = max(rows, key=lambda r: r["return_pct"])  # the strategy that has worked best on this stock
    range_name = request.args.get("range", DEFAULT_RANGE)
    if range_name not in RANGES:
        range_name = DEFAULT_RANGE

    closes = adjust_for_splits(stock["closes"])
    size = min(RANGES[range_name] or len(closes), len(closes))
    offset = len(closes) - size
    window = closes[offset:]
    marks = [(i - offset, kind) for i, kind in best["marks"] if i >= offset]

    return render_template(
        "stocks/detail.html",
        ticker=ticker,
        stock=stock,
        rows=rows,
        best=best,
        price=closes[-1],
        change_pct=(closes[-1] / closes[-2] - 1) * 100,
        up=window[-1] >= window[0],
        period=period_label(len(best["growth"])),
        ranges=list(RANGES),
        range_name=range_name,
        chart=build_chart(stock["dates"][offset:], marks=marks, price=window),
        watched=ticker in queries.watchlist_tickers(session, g.user.id),
    )
