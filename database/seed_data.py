""" 
Sample data population script for GroupX.
Populates Company, Stock, StockData, and Prediction tables with realistic sample data.
"""
from sqlalchemy.orm import Session

# Import all model classes for populating sample data
from backend.models import (
    User, Company, Stock, StockData, Prediction, 
    UserWatchlist, WatchlistItem
)

def populate_sample_data(session):
    """Creates sample data for schema models"""
    
    # ================
    # Sample Companies
    # ================
    if not session.query(Company).first():
        companies = [
            Company(name="Apple Inc.", sector="Technology", industry="Consumer Electronics", 
                   website="https://www.apple.com"),
            Company(name="Tesla Inc.", sector="Automotive", industry="Electric Vehicles",
                   website="https://www.tesla.com"),
            Company(name="Microsoft Corp", sector="Technology", industry="Software & Services",
                   website="https://www.microsoft.com"),
            Company(name="Amazon.com Inc.", sector="Retail", industry="E-Commerce",
                   website="https://www.amazon.com"),
        ]
        session.add_all(companies)
        session.commit()
    
    # =============
    # Sample Stocks
    # =============
    # Get the company objects after they're saved
    all_companies = Company.query.order_by(Company.id).all()
    apple = all_companies[0]  # Apple (first)
    tesla = all_companies[1]  # Tesla (second)
    microsoft = all_companies[2]  # Microsoft (third)
    amazon = all_companies[3]  # Amazon (fourth)
    
    if not apple or not tesla:
        print("Error: Could not retrieve companies for creating stocks")
        return
    
    stocks = [
        Stock(ticker="AAPL", company_id=apple.id, exchange_code="NASDAQ", currency="USD"),
        Stock(ticker="TSLA", company_id=tesla.id, exchange_code="NASDAQ", currency="USD"),
        Stock(ticker="MSFT", company_id=microsoft.id, exchange_code="NASDAQ", currency="USD"),
        Stock(ticker="AMZN", company_id=amazon.id, exchange_code="NASDAQ", currency="USD"),
    ]
    session.add_all(stocks)
    session.commit()
    
    print(f"✓ Added {len(stocks)} stocks")
    
    # =======================================================
    # Sample OHLCV Stock Data (7 days of data for each stock)
    # =======================================================
    dates = [
        "2024-01-05", "2024-01-06", "2024-01-08", "2024-01-09", 
        "2024-01-10", "2024-01-11", "2024-01-12"
    ]
    
    # AAPL sample OHLCV data
    apple_prices = [
        (65.20, 67.10, 66.80, 63.50, 95000),
        (66.80, 68.50, 65.90, 64.20, 88000),
        (67.50, 69.20, 66.80, 63.80, 102000),
        (68.10, 69.50, 67.20, 62.50, 97000),
        (63.90, 66.80, 63.50, 61.20, 110000),
        (61.80, 64.20, 61.00, 59.80, 105000),
        (60.50, 63.80, 60.20, 58.40, 118000)
    ]
    
    # TSLA sample OHLCV data
    tesla_prices = [
        (248.50, 255.20, 247.00, 238.80, 92000),
        (250.80, 258.60, 249.50, 245.20, 88000),
        (252.10, 260.30, 250.80, 237.50, 96000),
        (238.20, 245.80, 236.90, 230.50, 108000),
        (231.50, 240.20, 229.80, 224.60, 115000),
        (225.80, 235.40, 224.20, 218.90, 122000),
        (220.40, 231.80, 219.50, 212.60, 130000)
    ]
    
    # MSFT sample OHLCV data
    microsoft_prices = [
        (415.20, 422.80, 412.50, 405.60, 72000),
        (418.50, 428.30, 416.20, 410.80, 68000),
        (420.10, 429.50, 417.80, 404.20, 75000),
        (405.60, 418.90, 403.50, 398.20, 82000),
        (399.80, 412.50, 397.60, 391.40, 88000),
        (394.20, 405.80, 392.10, 386.50, 95000),
        (388.60, 399.40, 387.20, 380.80, 102000)
    ]
    
    # AMZN sample OHLCV data
    amazon_prices = [
        (178.50, 182.30, 176.80, 172.40, 55000),
        (180.20, 185.60, 178.90, 174.50, 52000),
        (183.10, 188.20, 180.50, 173.20, 58000),
        (174.80, 181.50, 172.60, 168.90, 65000),
        (170.20, 177.80, 168.50, 163.40, 72000),
        (167.80, 174.50, 165.20, 159.80, 78000),
        (164.20, 170.80, 163.10, 156.90, 85000)
    ]
    
    # Add all stock data records
    session.execute("DELETE FROM stock_data")
    
    for i in range(len(dates)):
        # AAPL records
        session.add(StockData(ticker="AAPL", date=dates[i], 
                             open=apple_prices[i][0], high=apple_prices[i][1], 
                             low=apple_prices[i][2], close=apple_prices[i][3],
                             volume=apple_prices[i][4]))
        
        # TSLA records
        session.add(StockData(ticker="TSLA", date=dates[i],
                             open=tesla_prices[i][0], high=tesla_prices[i][1], 
                             low=tesla_prices[i][2], close=tesla_prices[i][3],
                             volume=tesla_prices[i][4]))
        
        # MSFT records
        session.add(StockData(ticker="MSFT", date=dates[i],
                             open=microsoft_prices[i][0], high=microsoft_prices[i][1], 
                             low=microsoft_prices[i][2], close=microsoft_prices[i][3],
                             volume=microsoft_prices[i][4]))
        
        # AMZN records
        session.add(StockData(ticker="AMZN", date=dates[i],
                             open=amazon_prices[i][0], high=amazon_prices[i][1], 
                             low=amazon_prices[i][2], close=amazon_prices[i][3],
                             volume=amazon_prices[i][4]))
    
    session.commit()
    print(f"✓ Added {len(dates) * 4} stock data records (7 days × 4 stocks)")
    
    # ==================
    # Sample Predictions
    # ==================
    predictions = [
        Prediction(ticker="AAPL", prediction_date="2024-01-15", 
                  predicted_close=68.50, actual_close=67.90, confidence_score=0.82,
                  direction="buy"),
        Prediction(ticker="TSLA", prediction_date="2024-01-15",
                  predicted_close=225.00, actual_close=230.20, confidence_score=0.75,
                  direction="hold"),
        Prediction(ticker="MSFT", prediction_date="2024-01-15",
                  predicted_close=402.80, actual_close=398.50, confidence_score=0.88,
                  direction="buy"),
        Prediction(ticker="AMZN", prediction_date="2024-01-15",
                  predicted_close=162.40, actual_close=158.20, confidence_score=0.71,
                  direction="hold"),
    ]
    
    session.add_all(predictions)
    session.commit()
    print(f"✓ Added {len(predictions)} predictions")
    
    # ============================
    # Sample User & Watchlist Data
    # ============================
    # First check if user already exists, if not create one
    if not session.query(User).first():
        sample_user = User(username="john_doe", email="john@example.com",
                          password_hash="hashed_password_123", is_active=1)
        session.add(sample_user)
        session.commit()
    
    # Sample watchlist
    user = User.query.first()
    if user:
        watchlist = UserWatchlist(
            name="Tech Stocks",
            description="Apple, Microsoft tech company holdings"
        )
        
        session.add(watchlist)
        
        # Add items to watchlist
        stock1 = Stock.query.filter_by(ticker="AAPL").first()
        stock2 = Stock.query.filter_by(ticker="MSFT").first()
        
        if stock1:
            item1 = WatchlistItem(watchlist_id=watchlist.id, ticker=stock1.ticker)
            session.add(item1)
        
        if stock2:
            item2 = WatchlistItem(watchlist_id=watchlist.id, ticker=stock2.ticker)
            session.add(item2)
        
        session.commit()
        print(f"✓ Added 1 user with watchlist containing {len([stock1, stock2])} stocks")


if __name__ == "__main__":
    from sqlalchemy import create_engine
    db_url = 'sqlite:///GroupX.db'
    engine = create_engine(db_url, echo=False)
    
    print("Initializing sample data...")
    with Session(engine) as session:
        populate_sample_data(session)
    
    print("✓ Sample data initialization complete!")
