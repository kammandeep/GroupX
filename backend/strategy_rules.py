"""Four simple, rule-based strategies and a long-only backtest.

Pure Python: no Flask or database imports, so it can be tested on its own.
Each rule gets the most recent WARMUP closes (oldest first) and returns
(signal, why), where signal is "BUY", "SELL" or "HOLD".
"""

from statistics import mean, pstdev

WARMUP = 50           # closes every rule needs
BACKTEST_DAYS = 1260  # about 5 trading years
HORIZON = 5           # days ahead used to judge whether a BUY/SELL call was right
TRADING_DAYS_PER_YEAR = 252
SPLIT_TRIGGER = 1.8   # a one-day fall this big is a stock split, not a market move
SPLIT_RATIOS = (2, 3, 4, 5, 8, 10, 15, 20, 25, 30, 50)


def adjust_for_splits(closes):
    """Make a series of unadjusted closes continuous across stock splits.

    The stored prices are raw (a 20-for-1 split looks like a 95% crash), which
    would wreck every backtest, so scale everything before each split down.
    """
    adjusted = list(closes)
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > 0 and closes[i - 1] / closes[i] >= SPLIT_TRIGGER:
            ratio = closes[i - 1] / closes[i]
            factor = min(SPLIT_RATIOS, key=lambda r: abs(r - ratio))  # snap away market noise
            for j in range(i):
                adjusted[j] /= factor
    return adjusted


def momentum(closes):
    change = closes[-1] / closes[-21] - 1
    why = f"Price is {change:+.1%} over the last 20 days"
    return ("BUY" if change > 0.05 else "SELL" if change < -0.05 else "HOLD"), why


def mean_reversion(closes):
    window = closes[-20:]
    spread = pstdev(window)
    z = 0.0 if spread == 0 else (closes[-1] - mean(window)) / spread
    why = f"Price is {z:+.1f} standard deviations from its 20-day average"
    return ("BUY" if z < -1.5 else "SELL" if z > 1.5 else "HOLD"), why


def breakout(closes):
    prior = closes[-21:-1]
    if closes[-1] > max(prior):
        return "BUY", "Price just closed above its 20-day high"
    if closes[-1] < min(prior):
        return "SELL", "Price just closed below its 20-day low"
    return "HOLD", "Price is inside its 20-day range"


def trend_follow(closes):
    fast, slow = mean(closes[-20:]), mean(closes[-50:])
    if fast > slow:
        return "BUY", "20-day average is above the 50-day average"
    if fast < slow:
        return "SELL", "20-day average is below the 50-day average"
    return "HOLD", "20-day and 50-day averages are equal"


STRATEGIES = (
    {
        "slug": "momentum", "name": "Momentum", "rule": momentum,
        "summary": "Rides stocks that have been rising and steps aside from those that keep falling.",
        "steps": ("Buy when the price is up more than 5% over 20 days",
                  "Sell when it is down more than 5% over 20 days",
                  "Otherwise hold"),
    },
    {
        "slug": "mean-reversion", "name": "Mean reversion", "rule": mean_reversion,
        "summary": "Looks for stocks that moved too far, too fast and may swing back to normal.",
        "steps": ("Buy when the price is far below its 20-day average",
                  "Sell when it is far above its 20-day average",
                  "Otherwise hold"),
    },
    {
        "slug": "breakout", "name": "Breakout", "rule": breakout,
        "summary": "Acts when a stock escapes the price range it has been stuck in.",
        "steps": ("Buy when the price closes above its 20-day high",
                  "Sell when it closes below its 20-day low",
                  "Otherwise hold"),
    },
    {
        "slug": "trend-follow", "name": "Trend follow", "rule": trend_follow,
        "summary": "Follows the longer direction of the market using two moving averages.",
        "steps": ("Buy when the 20-day average is above the 50-day average",
                  "Sell when it is below",
                  "Otherwise hold"),
    },
)

BY_SLUG = {s["slug"]: s for s in STRATEGIES}


def today_signal(closes, rule):
    """(signal, why) for the latest close, or None if there is too little history."""
    if len(closes) < WARMUP:
        return None
    return rule(closes[-WARMUP:])


def backtest(closes, rule, days=BACKTEST_DAYS):
    """Replay `rule` over the last `days` closes as a long-only strategy.

    BUY enters, SELL exits, HOLD keeps the current position. Raises ValueError
    when there is too little history. `start` is the index in `closes` where the
    replay begins, so callers can line dates up with `growth`.
    """
    if len(closes) < WARMUP + 2:
        raise ValueError(f"need at least {WARMUP + 2} closes, got {len(closes)}")
    start = max(WARMUP, len(closes) - days)

    in_position = False
    entry_price = 0.0
    equity = peak = 1.0
    max_drop = 0.0
    calls = hits = trades = wins = 0
    growth = []
    marks = []  # (index into closes, "BUY" or "SELL") for each entry and exit

    for i in range(start, len(closes)):
        if in_position:
            equity *= closes[i] / closes[i - 1]
        peak = max(peak, equity)
        max_drop = min(max_drop, equity / peak - 1)
        growth.append(round(equity * 100, 2))

        signal, _ = rule(closes[i - WARMUP + 1:i + 1])
        if signal != "HOLD" and i + HORIZON < len(closes):
            calls += 1
            went_up = closes[i + HORIZON] > closes[i]
            hits += went_up if signal == "BUY" else not went_up
        if signal == "BUY" and not in_position:
            in_position, entry_price = True, closes[i]
            marks.append((i, "BUY"))
        elif signal == "SELL" and in_position:
            in_position = False
            marks.append((i, "SELL"))
            trades += 1
            wins += closes[i] > entry_price

    first = closes[start]
    return {
        "start": start,
        "growth": growth,
        "buy_hold": [round(c / first * 100, 2) for c in closes[start:]],
        "return_pct": round((equity - 1) * 100, 1),
        "max_drop_pct": round(max_drop * 100, 1),
        "accuracy_pct": round(hits / calls * 100) if calls else None,
        "win_rate_pct": round(wins / trades * 100) if trades else None,
        "trades": trades,
        "marks": marks,
    }


def period_label(sample_count):
    """'5y' for a full window, '2.5y' for a shorter one."""
    return f"{round(sample_count / TRADING_DAYS_PER_YEAR, 1):g}y"
