"""Populate the shared database with sample companies, prices, and predictions."""

from sqlalchemy import select

from backend.app import app
from backend.db import get_db
from backend.models import Company, Prediction, Stock, StockData, Strategy, TradingSignal

DATES = (
    "2024-01-05",
    "2024-01-06",
    "2024-01-08",
    "2024-01-09",
    "2024-01-10",
    "2024-01-11",
    "2024-01-12",
)

SAMPLE_COMPANIES = (
    ("AAPL", "Apple Inc.", "Technology", "Consumer Electronics", "https://www.apple.com"),
    ("TSLA", "Tesla Inc.", "Automotive", "Electric Vehicles", "https://www.tesla.com"),
    ("MSFT", "Microsoft Corp", "Technology", "Software & Services", "https://www.microsoft.com"),
    ("AMZN", "Amazon.com Inc.", "Retail", "E-Commerce", "https://www.amazon.com"),
)

SAMPLE_PRICES = {
    "AAPL": (
        (65.20, 67.10, 66.80, 63.50, 95000),
        (66.80, 68.50, 65.90, 64.20, 88000),
        (67.50, 69.20, 66.80, 63.80, 102000),
        (68.10, 69.50, 67.20, 62.50, 97000),
        (63.90, 66.80, 63.50, 61.20, 110000),
        (61.80, 64.20, 61.00, 59.80, 105000),
        (60.50, 63.80, 60.20, 58.40, 118000),
    ),
    "TSLA": (
        (248.50, 255.20, 247.00, 238.80, 92000),
        (250.80, 258.60, 249.50, 245.20, 88000),
        (252.10, 260.30, 250.80, 237.50, 96000),
        (238.20, 245.80, 236.90, 230.50, 108000),
        (231.50, 240.20, 229.80, 224.60, 115000),
        (225.80, 235.40, 224.20, 218.90, 122000),
        (220.40, 231.80, 219.50, 212.60, 130000),
    ),
    "MSFT": (
        (415.20, 422.80, 412.50, 405.60, 72000),
        (418.50, 428.30, 416.20, 410.80, 68000),
        (420.10, 429.50, 417.80, 404.20, 75000),
        (405.60, 418.90, 403.50, 398.20, 82000),
        (399.80, 412.50, 397.60, 391.40, 88000),
        (394.20, 405.80, 392.10, 386.50, 95000),
        (388.60, 399.40, 387.20, 380.80, 102000),
    ),
    "AMZN": (
        (178.50, 182.30, 176.80, 172.40, 55000),
        (180.20, 185.60, 178.90, 174.50, 52000),
        (183.10, 188.20, 180.50, 173.20, 58000),
        (174.80, 181.50, 172.60, 168.90, 65000),
        (170.20, 177.80, 168.50, 163.40, 72000),
        (167.80, 174.50, 165.20, 159.80, 78000),
        (164.20, 170.80, 163.10, 156.90, 85000),
    ),
}

SAMPLE_PREDICTIONS = (
    ("AAPL", 68.50, 67.90, 0.82, "up"),
    ("TSLA", 225.00, 230.20, 0.75, "flat"),
    ("MSFT", 402.80, 398.50, 0.88, "up"),
    ("AMZN", 162.40, 158.20, 0.71, "flat"),
)

#can add more sample strategies here with the name/description/model
SAMPLE_STRATEGIES = (
    ("Momentum", "Buys stocks the models expects to keep rising, sells one that is expectect to continue falling.", "XGBoost"), ("Mean reversion", "Looks for the stocks that have moved too far, too fast and may swing back.", "LSTM"),
)

#ticker/strategy name/signal/ confidence
SAMPLE_SIGNALS = (
    ("AAPL", "Momentum", "BUY", 0.82), ("AAPL", "Mean Reversion", "HOLD", 0.55),
    ("TSLA", "Momentum", "HOLD", 0.75), ("TSLA", "Mean Reversion", "BUY", 0.68),
    ("MSFT", "Momentum", "BUY", 0.88), ("MSFT", "Mean Reversion", "SELL", 0.61),
    ("AMZN", "Momentum", "SELL", 0.71), ("AMZN", "Mean Reversion", "HOLD", 0.58),
)

def populate_sample_data(session):
    companies = {
        company.name: company
        for company in session.scalars(select(Company)).all()
    }
    stocks = {
        stock.ticker: stock
        for stock in session.scalars(select(Stock)).all()
    }

    for ticker, name, sector, industry, website in SAMPLE_COMPANIES:
        company = companies.get(name)
        if company is None:
            company = Company(
                name=name, sector=sector, industry=industry, website=website
            )
            session.add(company)
            session.flush()
            companies[name] = company

        if ticker not in stocks:
            stock = Stock(
                ticker=ticker,
                company_id=company.id,
                exchange_code="NASDAQ",
                currency="USD",
            )
            session.add(stock)
            session.flush()
            stocks[ticker] = stock

    for ticker, rows in SAMPLE_PRICES.items():
        existing_dates = set(
            session.scalars(
                select(StockData.date).where(StockData.ticker == ticker)
            ).all()
        )
        for date, (open_price, high, close, low, volume) in zip(DATES, rows):  # rows are open, high, close, low, volume
            if date not in existing_dates:
                session.add(
                    StockData(
                        ticker=ticker,
                        date=date,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume,
                    )
                )

    existing_prediction_tickers = set(
        session.scalars(
            select(Prediction.ticker).where(
                Prediction.prediction_date == "2024-01-15"
            )
        ).all()
    )
    for ticker, predicted, actual, confidence, direction in SAMPLE_PREDICTIONS:
        if ticker not in existing_prediction_tickers:
            session.add(
                Prediction(
                    ticker=ticker,
                    prediction_date="2024-01-15",
                    predicted_close=predicted,
                    actual_close=actual,
                    confidence_score=confidence,
                    direction=direction,
                )
            )

    strategies = {st.name: st for st in session.scalars(select(Strategy)).all()}
    for name, description, model_name in SAMPLE_STRATEGIES:
        if name not in strategies:
            strategies[name] = Strategy(name=name, description=description, model_name=model_name)
            session.add(strategies[name])
    session.flush()

    existing_signals = set(session.execute(
        select(TradingSignal.ticker, TradingSignal.strategy_id).where(TradingSignal.signal_date == DATES[-1])
    ).all())
    for ticker, strategy_name, signal, confidence in SAMPLE_SIGNALS:
        strategy = strategies[strategy_name]
        if (ticker, strategy.id) not in existing_signals:
            session.add(TradingSignal(ticker=ticker, strategy_id=strategy.id, signal_date=DATES[-1],
                                      signal_type=signal, confidence_score=confidence, model_name=strategy.model_name))
    session.commit()


if __name__ == "__main__":
    with app.app_context():
        populate_sample_data(get_db())
    print("Sample stock data is ready in the configured database.")
