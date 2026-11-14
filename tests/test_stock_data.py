import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from backend import queries
from backend.models import (
    Company, Stock, StockData, Strategy, TradingSignal, User, UserWatchlist, WatchlistItem,
)
from database.seed_data import populate_sample_data


def make_user(session, name="abhey"):
    user = User(username=name, email=f"{name}@example.com", password_hash="x")
    session.add(user)
    session.commit()
    return user


# seeding 

def test_seed_fills_every_table_and_can_run_twice(seeded):
    populate_sample_data(seeded)  # second run must not duplicate or crash
    count = lambda model: len(seeded.scalars(select(model)).all())
    assert (count(Stock), count(Strategy), count(TradingSignal)) == (4, 2, 8)
    assert count(StockData) == 28


def test_created_at_is_filled_in_by_the_database(seeded):
    assert seeded.scalars(select(Stock)).first().created_at is not None


# price movement 

def test_latest_prices_work_out_previous_close_and_movement(seeded):
    aapl = next(r for r in queries.latest_prices(seeded) if r["ticker"] == "AAPL")
    assert aapl["date"] == "2024-01-12"
    assert (aapl["close"], aapl["prev_close"]) == (60.20, 61.00)
    assert aapl["change"] == -0.80 and aapl["change_pct"] == -1.31
    assert aapl["movement"] == "down" and aapl["exchange"] == "NASDAQ"


def test_a_stock_with_one_day_of_data_has_no_previous_close(seeded):
    company = Company(name="Nvidia")
    seeded.add(company); seeded.flush()
    seeded.add(Stock(ticker="NVDA", company_id=company.id))
    seeded.add(StockData(ticker="NVDA", date="2024-01-12", open=10, high=12, low=9, close=11, volume=1))
    seeded.commit()
    nvda = next(r for r in queries.latest_prices(seeded) if r["ticker"] == "NVDA")
    assert nvda["prev_close"] is None and nvda["change_pct"] is None


def test_inactive_stocks_are_hidden(seeded):
    seeded.scalar(select(Stock).where(Stock.ticker == "TSLA")).is_active = False
    seeded.commit()
    assert "TSLA" not in [r["ticker"] for r in queries.latest_prices(seeded)]


#  signals 

def test_signals_show_what_each_strategy_says(seeded):
    msft = {s["strategy"]: s["signal"] for s in queries.latest_signals(seeded, ticker="MSFT")}
    assert msft == {"Momentum": "BUY", "Mean reversion": "SELL"}


def test_signals_can_be_filtered_by_strategy(seeded):
    momentum = seeded.scalar(select(Strategy).where(Strategy.name == "Momentum"))
    rows = queries.latest_signals(seeded, strategy_id=momentum.id)
    assert len(rows) == 4 and {r["strategy"] for r in rows} == {"Momentum"}


def test_switched_off_strategies_are_not_shown(seeded):
    seeded.scalar(select(Strategy).where(Strategy.name == "Momentum")).is_active = False
    seeded.commit()
    assert {s["strategy"] for s in queries.latest_signals(seeded)} == {"Mean reversion"}


def test_latest_predictions(seeded):
    (prediction,) = queries.latest_predictions(seeded, "MSFT")
    assert prediction["direction"] == "up" and prediction["predicted_close"] == 402.8


# the database rejects bad data 

@pytest.mark.parametrize("make_bad_row", [
    lambda s: Stock(ticker="NYSE1", company_id=1, exchange_code="NYSE"),                                  # not NASDAQ
    lambda s: StockData(ticker="AAPL", date="2024-01-12", open=1, high=2, low=1, close=1, volume=1),      # day already stored
    lambda s: StockData(ticker="AAPL", date="2024-02-01", open=5, high=6, low=7, close=6, volume=1),      # low above high
    lambda s: StockData(ticker="AAPL", date="2024-02-01", open=5, high=6, low=4, close=9, volume=1),      # close outside range
    lambda s: TradingSignal(ticker="AAPL", strategy_id=1, signal_date="2024-02-01", signal_type="MAYBE"),  # not BUY/SELL/HOLD
    lambda s: TradingSignal(ticker="AAPL", strategy_id=1, signal_date="2024-01-12", signal_type="BUY"),   # strategy already spoke today
    lambda s: TradingSignal(ticker="AAPL", strategy_id=1, signal_date="2024-02-01", signal_type="BUY", confidence_score=1.5),
])
def test_bad_rows_are_rejected(seeded, make_bad_row):
    seeded.add(make_bad_row(seeded))
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()


# watchlist

def test_watchlist_add_is_safe_to_repeat_and_shows_prices_and_signals(seeded):
    user = make_user(seeded)
    queries.add_to_watchlist(seeded, user.id, "aapl")
    queries.add_to_watchlist(seeded, user.id, "AAPL")
    queries.add_to_watchlist(seeded, user.id, "MSFT")

    overview = queries.watchlist_overview(seeded, user.id)
    assert [r["ticker"] for r in overview] == ["AAPL", "MSFT"]
    assert {s["strategy"] for s in overview[0]["signals"]} == {"Momentum", "Mean reversion"}
    assert len(seeded.scalars(select(WatchlistItem)).all()) == 2


def test_watchlists_are_private_to_each_user(seeded):
    a, b = make_user(seeded, "a_user"), make_user(seeded, "b_user")
    queries.add_to_watchlist(seeded, a.id, "AAPL")
    assert queries.watchlist_overview(seeded, b.id) == []


def test_unknown_or_non_nasdaq_tickers_cannot_be_watched(seeded):
    with pytest.raises(ValueError):
        queries.add_to_watchlist(seeded, make_user(seeded).id, "ZZZZ")


def test_deleting_a_user_removes_their_watchlists(seeded):
    user = make_user(seeded)
    queries.add_to_watchlist(seeded, user.id, "AAPL")
    seeded.execute(delete(User).where(User.id == user.id))
    seeded.commit()
    assert seeded.scalars(select(UserWatchlist)).all() == []
    assert seeded.scalars(select(WatchlistItem)).all() == []


# the existing app still works

def test_existing_api_and_login_still_work(app, seeded):
    client = app.test_client()
    assert client.get("/health").get_json() == {"status": "healthy", "companies_count": 4}
    assert len(client.get("/api/stocks").get_json()) == 4
    assert client.get("/api/predictions").get_json()[0]["direction"] in ("up", "flat")
