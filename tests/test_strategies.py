import pytest

from backend import queries
from backend.models import Company, Stock, StockData, User
from backend.strategy_rules import (
    STRATEGIES, WARMUP, adjust_for_splits, backtest, breakout, mean_reversion, momentum, today_signal, trend_follow,
)

FLAT = [100.0] * WARMUP


def rising(n=WARMUP, step=1.0):
    return [100 + i * step for i in range(n)]


# test rules (pure, no database)

def test_momentum_buys_a_rise_and_sells_a_fall():
    assert momentum(rising())[0] == "BUY"
    assert momentum(rising(step=-1.0))[0] == "SELL"
    assert momentum(FLAT)[0] == "HOLD"


def test_mean_reversion_buys_a_sudden_drop_and_sells_a_sudden_jump():
    assert mean_reversion(FLAT[:-1] + [80.0])[0] == "BUY"
    assert mean_reversion(FLAT[:-1] + [120.0])[0] == "SELL"
    assert mean_reversion(FLAT)[0] == "HOLD"  # no spread must not divide by zero


def test_breakout_needs_a_new_20_day_high_or_low():
    assert breakout(FLAT[:-1] + [101.0])[0] == "BUY"
    assert breakout(FLAT[:-1] + [99.0])[0] == "SELL"
    assert breakout(FLAT)[0] == "HOLD"


def test_trend_follow_compares_the_20_and_50_day_averages():
    assert trend_follow(rising())[0] == "BUY"
    assert trend_follow(rising(step=-1.0))[0] == "SELL"
    assert trend_follow(FLAT)[0] == "HOLD"


def test_today_signal_is_none_without_enough_history():
    assert today_signal(rising(WARMUP - 1), momentum) is None


#split adjustment

def test_a_split_is_not_treated_as_a_crash():
    assert adjust_for_splits([100.0, 100.0, 25.0, 26.0]) == [25.0, 25.0, 25.0, 26.0]


def test_a_noisy_split_snaps_to_the_real_ratio():
    # 20-for-1 plus a 2% market move is a 19.6x fall, still a 20-for-1 split
    adjusted = adjust_for_splits([2000.0, 102.0])
    assert adjusted[0] == pytest.approx(100.0)


def test_normal_moves_are_left_alone():
    assert adjust_for_splits([100.0, 90.0, 95.0]) == [100.0, 90.0, 95.0]
    assert adjust_for_splits([]) == []


# backtest

def test_backtest_rejects_too_little_history():
    with pytest.raises(ValueError):
        backtest(rising(WARMUP), momentum)


def test_backtest_of_a_steady_climb_gains_and_never_drops():
    result = backtest(rising(120), trend_follow)
    assert result["return_pct"] > 0 and result["max_drop_pct"] == 0
    assert len(result["growth"]) == len(result["buy_hold"]) >= 2


def test_every_strategy_runs_on_the_same_history():
    closes = [100 + (i % 7) * 3 + i * 0.2 for i in range(200)]
    for strategy in STRATEGIES:
        assert backtest(closes, strategy["rule"])["growth"][0] == 100


#database + pages

def add_stock(session, ticker, closes):
    company = Company(name=f"{ticker} Corp")
    session.add(company)
    session.flush()
    session.add(Stock(ticker=ticker, company_id=company.id))
    session.add_all(
        StockData(ticker=ticker, date=f"2024-{1 + i // 28:02d}-{1 + i % 28:02d}",
                  open=c, high=c, low=c, close=c, volume=1)
        for i, c in enumerate(closes)
    )
    session.commit()


@pytest.fixture
def client(app, seeded):
    client = app.test_client()
    user = User(username="abhey", email="abhey@example.com", password_hash="x")
    seeded.add(user)
    seeded.commit()
    with client.session_transaction() as flask_session:
        flask_session["user_id"] = user.id
    return client


def test_close_series_is_oldest_first_and_keeps_only_the_newest_rows(seeded):
    add_stock(seeded, "NVDA", rising(10))
    series = queries.close_series(seeded, 5)
    assert series["NVDA"]["closes"] == rising(10)[-5:]
    assert series["NVDA"]["dates"] == sorted(series["NVDA"]["dates"])


def test_stock_search_lists_everything_then_filters(client):
    assert len(client.get("/api/stock-search").json["stocks"]) == 4
    assert [s["ticker"] for s in client.get("/api/stock-search?q=apple").json["stocks"]] == ["AAPL"]


def test_stock_search_returns_nothing_for_an_unlisted_stock(client):
    assert client.get("/api/stock-search?q=zzzz").json["stocks"] == []


def test_stock_search_dialog_provides_stock_detail_url(client):
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b'data-stock-url="/stocks/TICKER"' in response.data


def test_stock_search_needs_a_login(app):
    assert app.test_client().get("/api/stock-search").status_code == 302


def test_strategy_pages_show_signals_for_stocks_with_history(client, seeded):
    add_stock(seeded, "NVDA", rising(80))
    assert b"Momentum" in client.get("/strategies").data
    detail = client.get("/strategies/momentum")
    assert detail.status_code == 200 and b"NVDA" in detail.data and b"BUY" in detail.data


def test_strategy_detail_explains_when_there_is_no_history(client):
    # the sample data only has 7 days per stock
    assert b"No price history yet" in client.get("/strategies/breakout").data


def test_stock_detail_renders_after_search_result_is_selected(client, seeded):
    add_stock(seeded, "NVDA", rising(80))
    response = client.get("/stocks/NVDA")
    assert response.status_code == 200
    assert b"All strategies on NVDA" in response.data


def test_unknown_strategy_is_a_404(client):
    assert client.get("/strategies/nope").status_code == 404
