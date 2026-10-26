"""
Connects Flask (web framework) with SQLAlchemy and SQLite schema
"""

from flask import Flask, render_template
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, DeclarativeBase

# ====================================
# Step 1: Flask App Object
# ====================================
app = Flask(__name__)

# ============================================
# Step 2: Engine & Base Class
# ============================================
db_url = 'sqlite:///GroupX.db'
engine = create_engine(
    db_url,
    echo=False  # Set to True to see SQL queries in real-time
)

Base = DeclarativeBase()  # Base class for all model classes

# ============================================
# Step 3: Import Model Classes from models.py
# ============================================
from models import User, Company, Stock, StockData, Prediction, UserWatchlist, WatchlistItem, TradingSignal

# Helper function to get any model class by name
def get_model_class(model_name):
    return {m.__name__: m for m in [
        User, Company, Stock, StockData, Prediction, 
        UserWatchlist, WatchlistItem, TradingSignal
    ]}.get(model_name)

# ========================================================
# Step 4: Initialize Database (create tables + load data)
# ========================================================
def init_db():
    """Creates all database tables from model classes and loads seed data"""
    print("Initializing database...")
    
    with Session(engine) as session:
        Base.metadata.create_all(bind=engine)  # Creates tables automatically!
        
        from seed_data import populate_sample_data
        populate_sample_data(session)
    
    print(f"✓ Database initialized: {db_url}")

# =====================================
# Step 5: Define Routes (URL Handlers)
# =====================================

@app.route('/')  # The home page
def index():
    """Main dashboard HTML"""
    return render_template('dashboard.html')  # Loads your existing HTML file

@app.route('/api/stocks', methods=['GET'])  # Returns stock data as JSON
def get_stocks():
    """Gets all stocks and returns them as JSON for frontend"""
    with Session(engine) as session:
        companies = Company.query.all()
        model_classes = {m.__name__: m for m in [Company, Stock]}
        
        result = []
        for company in companies:
            model = model_classes.get(company.__class__.__name__, Stock)
            stocks = model.query.filter_by(company_id=company.id).all()
            
            for stock in stocks:
                result.append({
                    'id': stock.id,
                    'ticker': stock.ticker,
                    'company_name': company.name,
                    'exchange_code': stock.exchange_code,
                    'current_price': get_latest_close(stock)
                })
    
    return result

@app.route('/api/stocks/<int:stock_id>', methods=['GET'])  # Get specific stock info
def get_stock(stock_id):
    """Getting specific stock's information"""
    Stock = get_model_class('Stock')
    try:
        stock = Stock.query.get_or_404(stock_id)
        return {'error': 'Stock not found'}
    except Exception as e:
        return str(e)

@app.route('/api/stocks/<int:stock_id>/close', methods=['GET'])  # Get current price
def get_stock_close(stock_id):
    """Getting the latest closing price for a stock"""
    StockData = get_model_class('StockData')
    
    try:
        with Session(engine) as session:
            model_classes = {m.__name__: m for m in [Company, Stock, StockData]}
            
            company_obj = Company.query.get(stock_id)
            if not company_obj:
                return None
            
            company_model = model_classes.get(company_obj.__class__.__name__, Stock)
            stock = company_model.query.get(stock_id)
            if not stock:
                return None
            
            latest_prices = StockData.query.filter_by(ticker=stock.ticker).order_by(
                StockData.date.desc()
            ).first()
            
            return {'price': latest_prices.close if latest_prices else 0}
    except Exception as e:
        print(f"Error getting stock close: {e}")
        return None

@app.route('/api/stock-data', methods=['GET'])  # Get recent price history
def get_stock_data():
    """Returns recent OHLCV data for all stocks"""
    StockData = get_model_class('StockData')
    
    try:
        with Session(engine) as session:
            model_classes = {m.__name__: m for m in [Company, Stock, StockData]}
            
            company_objs = Company.query.all()
            result = []
            
            for company in company_objs:
                company_model = model_classes.get(company.__class__.__name__, Stock)
                stocks = company_model.query.filter_by(company_id=company.id).all()
                
                for stock in stocks:
                    latest_prices = StockData.query.filter_by(ticker=stock.ticker).order_by(
                        StockData.date.desc()
                    ).limit(7).all()  # Get last 7 days
                    
                    data = []
                    for price in latest_prices:
                        data.append({
                            'date': price.date,
                            'open': round(price.open, 2),
                            'high': round(price.high, 2),
                            'low': round(price.low, 2),
                            'close': round(price.close, 2),
                            'volume': price.volume
                        })
                    
                    if data:
                        result.append({'ticker': stock.ticker, 'data': data})
    
    return result

@app.route('/api/predictions', methods=['GET'])  # Get all predictions
def get_predictions():
    """Returns recent model predictions"""
    Prediction = get_model_class('Prediction')
    
    try:
        with Session(engine) as session:
            model_classes = {m.__name__: m for m in [Company, Stock, Prediction]}
            
            preds = Prediction.query.all()
            result = []
            
            for pred in preds:
                stock = get_model_class('Stock').query.get(pred.ticker)
                if stock and model_classes.get(stock.__class__.__name__, Stock):
                    company_obj = StockData  # Using stock's company_id
                    company_name = None
                    if company_obj.company_id:
                        company_obj = Company.query.get(company_obj.company_id)
                        company_name = company_obj.name if company_obj else "Unknown"
                    
                    result.append({
                        'ticker': pred.ticker,
                        'prediction_date': pred.prediction_date,
                        'predicted_close': pred.predicted_close,
                        'actual_close': pred.actual_close,
                        'confidence_score': pred.confidence_score,
                        'direction': pred.direction,
                        'company_name': company_name
                    })
    
    return result

@app.route('/api/companies', methods=['GET'])  # Get all companies
def get_companies():
    """Returns list of all companies"""
    Company = get_model_class('Company')
    
    with Session(engine) as session:
        companies = Company.query.all()
        result = []
        
        for company in companies:
            stock = Stock.query.filter_by(company_id=company.id).first()
            
            result.append({
                'id': company.id,
                'name': company.name,
                'sector': company.sector,
                'industry': company.industry,
                'website': company.website
            })
    
    return result

@app.route('/health', methods=['GET'])  # Health check endpoint
def health():
    """Simple API to check if app is running"""
    try:
        with Session(engine) as session:
            count = Company.query.count()
            return {'status': 'healthy', 'companies_count': count}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}

# =================
# Helper Functions
# =================
def get_latest_close(stock):
    """Getting the latest closing price for a stock"""
    StockData = get_model_class('StockData')
    
    company_obj = Stock.query.get(stock.company_id)
    if not company_obj:
        return None
    
    from models import StockData
    latest_prices = StockData.query.filter_by(ticker=stock.ticker).order_by(
        StockData.date.desc()
    ).first()
    
    return latest_prices.close if latest_prices else 0

# ====================
# Run the Application
# ====================
if __name__ == '__main__':
    # Initialize database (create tables + load sample data)
    init_db()
    
    print("Starting Flask application...")
    app.run(debug=True, use_reloader=False)  # debug=True for error messages
