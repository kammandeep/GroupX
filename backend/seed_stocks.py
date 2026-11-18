from sqlalchemy import select

from .app import app
from . import db
from .models import Company, Stock, StockData

NAMES = {
    "AAPL": "Apple Inc.", "AMZN": "Amazon.com Inc.", "GOOGL": "Alphabet Inc.",
    "MSFT": "Microsoft Corp", "NVDA": "Nvidia Corp",
}

def seed():
    with app.app_context():
        session = db.get_db()
        known =set(session.scalars(select(Stock.ticker)))
        tickers = set(session.scalars(select(StockData.ticker).distinct()))
        
        added = 0
        
        for ticker in sorted(tickers - known):
            name = NAMES.get(ticker, ticker)
            company = session.scalar(select(Company).where(Company.name == name))
            if company is None:
                company = Company(name=name)
                session.add(company)
                session.flush()
            session.add(Stock(ticker=ticker, company_id=company.id, exchange_code='NASDAQ', currency="USD", is_active=True))
            added += 1
        session.commit()
        print(f"Added {added} stocks")

if __name__ == "__main__":
    seed()