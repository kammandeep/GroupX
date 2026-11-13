# ========================
# Flask SQLAlchemy Models
# ========================
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    REAL,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

# Base class 
Base = declarative_base()

# =====================
# SECTION 1: USER MODEL
# =====================
class User(Base):
    __tablename__ = 'users'  # Must match your SQL table name exactly!
    
    id = Column(Integer, primary_key=True)                       # Auto-increment ID
    username = Column(String(50), unique=True, nullable=False)   # Login username
    email = Column(String(100), unique=True, nullable=False)     # Email for communication
    password_hash = Column(String(256), nullable=False)          # Hashed password
    created_at = Column(TIMESTAMP, default=None)                 # Database timestamp
    updated_at = Column(TIMESTAMP, default=None)
    last_login_at = Column(TIMESTAMP, nullable=True)
    is_active = Column(Integer, default=1)                       # 1 = active, 0 = inactive


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    experience_level = Column(String(20), default="beginner", nullable=False)
    risk_comfort = Column(String(20), default="medium", nullable=False)
    signal_alerts = Column(Boolean, default=True, nullable=False)
    daily_summary = Column(Boolean, default=True, nullable=False)
    strategy_updates = Column(Boolean, default=False, nullable=False)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticker = Column(String(10), nullable=False)
    condition = Column(String(100), nullable=False)
    destination = Column(String(20), default="app", nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        UniqueConstraint("rule_id", "signal_id", name="uq_alert_event_rule_signal"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    signal_id = Column(Integer, ForeignKey("trading_signals.id"), nullable=False)
    title = Column(String(160), nullable=False)
    detail = Column(String(255), nullable=False)
    tone = Column(String(20), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False)


# =========================
# SECTION 2: COMPANY MODEL
# =========================
class Company(Base):
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)          # Company full name
    sector = Column(Text)                               # Sector (e.g., Technology)
    industry = Column(Text)                             # Industry sub-category  
    website = Column(Text)                              # Company website URL
    created_at = Column(TIMESTAMP, default=None)

# =======================
# SECTION 3: STOCK MODEL  
# =======================
class Stock(Base):
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), unique=True, nullable=False)  # e.g., 'AAPL', 'TSLA'
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)  # Foreign key to companies
    exchange_code = Column(String(10), default='NYSE')      # Stock exchange code
    currency = Column(String(3), default='USD')             # Trading currency (USD, EUR, JPY)
    is_active = Column(Boolean, default=True)               # Market active/inactive status
    created_at = Column(TIMESTAMP, default=None)

# ====================================================================
# SECTION 4: STOCK DATA MODEL (OHLCV - Open, High, Low, Close, Volume)
# ====================================================================
class StockData(Base):
    __tablename__ = 'stock_data'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)  # Reference to stocks table
    date = Column(String(10), nullable=False)                                 # Trading date in YYYY-MM-DD format
    open = Column(REAL, nullable=False)                                       # Opening price
    high = Column(REAL, nullable=False)                                       # Day's highest price
    low = Column(REAL, nullable=False)                                        # Day's lowest price
    close = Column(REAL, nullable=False)                                      # Closing price (most important!)
    volume = Column(Integer, default=0)                                       # Number of shares traded
    created_at = Column(TIMESTAMP, default=None)

# ============================
# SECTION 5: PREDICTION MODEL  
# ============================
class Prediction(Base):
    __tablename__ = 'predictions'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)  # Reference to stocks table
    prediction_date = Column(String(10), nullable=False)                      # Date the model predicted for
    predicted_close = Column(REAL, nullable=False)                            # Predicted closing price
    actual_close = Column(REAL)                                               # Actual price (filled after market closes)
    confidence_score = Column(REAL, default=0.0)                              # Model's confidence (0-1 scale)
    direction = Column(String(20), default='neutral')                         # 'buy', 'sell' or 'hold' recommendation
    prediction_type = Column(String(50), default='daily')                     # Frequency: daily/weekly/monthly
    model_name = Column(String(100), default='baseline')                      # Which ML model created this prediction
    created_at = Column(TIMESTAMP, default=None)

# =========================================================
# SECTION 6: WATCHLIST MODELS (Many-to-Many relationships)
# =========================================================
class UserWatchlist(Base):
    __tablename__ = 'user_watchlists'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)     # Foreign key to users table
    name = Column(String(100), nullable=False)                            # e.g., 'Tech Portfolio', 'Growth Stocks'
    description = Column(Text)                                            # Optional notes about this watchlist
    created_at = Column(TIMESTAMP, default=None)

class WatchlistItem(Base):
    __tablename__ = 'watchlist_items'
    
    id = Column(Integer, primary_key=True)
    watchlist_id = Column(Integer, ForeignKey('user_watchlists.id'), nullable=False)  # Foreign key to watchlists
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)          # Foreign key to stocks (unique combination)
    added_at = Column(TIMESTAMP, default=None)

# =================================
# SECTION 7: TRADING SIGNALS MODEL  
# =================================
class TradingSignal(Base):
    __tablename__ = 'trading_signals'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    signal_type = Column(String(20), nullable=False)   # 'BUY', 'SELL' or 'HOLD'
    confidence_score = Column(REAL, default=0.0)       # Signal strength (0-1 scale)
    target_price = Column(REAL)                        # Optional price target
    model_name = Column(String(100))                   # Which ML model generated this signal
    signal_timestamp = Column(TIMESTAMP, default=None)

# ====================================
# SECTION 8: SIGNAL FLAGS & GUARDRAILS  
# ====================================

class SignalFlag(Base):
    __tablename__ = 'signal_flags'
    
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, ForeignKey('trading_signals.id'), nullable=False)
    flag_type = Column(String(50), nullable=False)  # Types of guardrails


class SignalReviewStatus(Base):
    __tablename__ = 'signal_review_status'
    
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, ForeignKey('trading_signals.id'), nullable=False)
    review_state = Column(String(50), nullable=False)  # Review level


class SignalOverride(Base):
    __tablename__ = 'signal_overrides'
    
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, ForeignKey('trading_signals.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    override_reason = Column(Text)                      # Why human made this decision
    original_signal = Column(String(50), default='neutral')
    human_decision = Column(String(20), nullable=False)  # Human's final decision
    