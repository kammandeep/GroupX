"""Strategy pages: a list of the four strategies and a detail page for each."""

from collections import Counter

from flask import Blueprint, abort, render_template, request

from . import db, queries
from .auth import login_required
from .strategy_rules import (
    BACKTEST_DAYS, BY_SLUG, STRATEGIES, WARMUP,
    adjust_for_splits, backtest, period_label, today_signal,
)

bp = Blueprint("strategies", __name__)

# Chart geometry in SVG units (the page scales it to fit).
CHART_W, CHART_H = 820, 340
PAD_L, PAD_R, PAD_T, PAD_B = 52, 12, 12, 30


def analyse(strategy, series):
    """Today's signal plus a backtest for every stock with enough price history."""
    results = []
    for ticker, stock in series.items():
        if len(stock["closes"]) < WARMUP + 2:
            continue
        closes = adjust_for_splits(stock["closes"])
        signal, why = today_signal(closes, strategy["rule"])
        result = backtest(closes, strategy["rule"])
        results.append({
            "ticker": ticker, "name": stock["name"], "signal": signal, "why": why,
            "dates": stock["dates"][result["start"]:], **result,
        })
    return results


def average(results, key):
    values = [r[key] for r in results if r[key] is not None]
    return sum(values) / len(values) if values else None


def period_of(results):
    return period_label(len(results[0]["growth"]) if results else BACKTEST_DAYS)


def build_chart(result):
    """Growth-of-100 lines as SVG points. Drawn server-side, so no chart library is needed."""
    values = result["growth"] + result["buy_hold"]
    low, high = min(values), max(values)
    span = (high - low) or 1
    plot_w, plot_h = CHART_W - PAD_L - PAD_R, CHART_H - PAD_T - PAD_B
    last = len(result["growth"]) - 1  # backtest() guarantees at least two points

    def points(series):
        return " ".join(
            f"{i / last * plot_w:.1f},{plot_h - (v - low) / span * plot_h:.1f}"
            for i, v in enumerate(series)
        )

    return {
        "width": CHART_W, "height": CHART_H, "left": PAD_L, "top": PAD_T,
        "plot_w": plot_w, "plot_h": plot_h,
        "strategy": points(result["growth"]),
        "buy_hold": points(result["buy_hold"]),
        "y_ticks": [(plot_h - k / 4 * plot_h, f"{low + span * k / 4:.0f}") for k in range(5)],
        "x_ticks": [(i / last * plot_w, result["dates"][i]) for i in (0, last // 2, last)],
    }


@bp.get("/strategies")
@login_required
def strategy_list():
    series = queries.close_series(db.get_db(), BACKTEST_DAYS + WARMUP)
    cards = []
    for strategy in STRATEGIES:
        results = analyse(strategy, series)
        cards.append({
            "strategy": strategy,
            "period": period_of(results),
            "stock_count": len(results),
            "signal_counts": Counter(r["signal"] for r in results),
            "accuracy": average(results, "accuracy_pct"),
            "return_pct": average(results, "return_pct"),
            "win_rate": average(results, "win_rate_pct"),
        })
    return render_template("strategies/strategies.html", cards=cards)


@bp.get("/strategies/<slug>")
@login_required
def strategy_detail(slug):
    strategy = BY_SLUG.get(slug)
    if strategy is None:
        abort(404)

    series = queries.close_series(db.get_db(), BACKTEST_DAYS + WARMUP)
    results = analyse(strategy, series)

    wanted = request.args.get("ticker", "").strip().upper()
    selected = next((r for r in results if r["ticker"] == wanted), results[0] if results else None)

    return render_template(
        "strategies/detail.html",
        strategy=strategy,
        results=results,
        selected=selected,
        chart=build_chart(selected) if selected else None,
        period=period_of(results),
        min_days=WARMUP + 2,
    )
