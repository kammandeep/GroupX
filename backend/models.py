# ========================
# Flask SQLAlchemy Models
# ========================
from sqlalchemy import Column, Integer, String, Text, REAL, Boolean, TIMESTAMP, ForeignKey, Index, Integer, String, Text, UniqueConstraint, CheckConstraint, func

from sqlalchemy.orm import declarative_base

# Base class 
Base = declarative_base()

MARKET = "NASDAQ" # the app only covers this exchange

# =====================
# SECTION 1: USER MODEL
# =====================
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)          # never the password itself
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)  # filled in by the database
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(TIMESTAMP, nullable=True)
    is_active = Column(Integer, default=1, nullable=False)       # 1 = active, 0 = disabled


class UserProfile(Base):
    __tablename__ = 'user_profiles'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    goal = Column(String(20))               
    experience_level = Column(String(20))    
    completed_at = Column(TIMESTAMP)         
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

# =========================
# SECTION 2: COMPANY MODEL
# =========================
class Company(Base):
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)
    sector = Column(Text)
    industry = Column(Text)
    website = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


# =======================
# SECTION 3: STOCK MODEL
# =======================
class Stock(Base):
    """One row per NASDAQ ticker we track. Other tables point at it by ticker."""
    __tablename__ = 'stocks'
    __table_args__ = (
        CheckConstraint(f"exchange_code = '{MARKET}'", name="ck_stocks_nasdaq_only"),
    )

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), unique=True, nullable=False)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    exchange_code = Column(String(10), default=MARKET, nullable=False)   # the market it trades on
    currency = Column(String(3), default='USD', nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)            # False = stop showing it
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


# ====================================================================
# SECTION 4: STOCK DATA (one row per stock per trading day: OHLCV)
# ====================================================================
class StockData(Base):
    """Daily prices. "Previous day close" and "price movement" are NOT stored:
    they are worked out from these rows (see queries.py), so they can never disagree."""
    __tablename__ = 'stock_data'
    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uq_stock_data_ticker_date'),  # one row per day, also the lookup index
        CheckConstraint('low <= high AND open BETWEEN low AND high AND close BETWEEN low AND high',
                        name='ck_stock_data_prices_make_sense'),
        CheckConstraint('volume >= 0', name='ck_stock_data_volume'),
    )

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    date = Column(String(10), nullable=False)    # 'YYYY-MM-DD' (text in this format sorts correctly)
    open = Column(REAL, nullable=False)
    high = Column(REAL, nullable=False)
    low = Column(REAL, nullable=False)
    close = Column(REAL, nullable=False)
    volume = Column(Integer, default=0, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


# ============================
# SECTION 5: PREDICTION MODEL
# ============================
class Prediction(Base):
    """What a model forecasts for one stock on one day. It is a PRICE forecast;
    buy/sell/hold decisions live in trading_signals."""
    __tablename__ = 'predictions'
    __table_args__ = (
        UniqueConstraint('ticker', 'prediction_date', 'model_name', name='uq_prediction_per_model_day'),
        CheckConstraint("direction IN ('up', 'down', 'flat')", name='ck_prediction_direction'),
        CheckConstraint('confidence_score BETWEEN 0 AND 1', name='ck_prediction_confidence'),
    )

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    prediction_date = Column(String(10), nullable=False)       # the day being predicted
    predicted_close = Column(REAL, nullable=False)
    actual_close = Column(REAL)                                # filled in once the day is over
    confidence_score = Column(REAL, default=0.0, nullable=False)   # 0 to 1
    direction = Column(String(10), default='flat', nullable=False)  # expected price movement
    prediction_type = Column(String(50), default='daily', nullable=False)
    model_name = Column(String(100), default='baseline', nullable=False)  # e.g. 'xgboost', 'lstm'
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


# ===========================
# SECTION 5B: STRATEGY MODEL
# ===========================
class Strategy(Base):
    """A named way of turning predictions and market trends into signals."""
    __tablename__ = 'strategies'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)    # e.g. 'Momentum'
    description = Column(Text)                                 # plain-English explanation shown to users
    model_name = Column(String(100))                           # which model feeds it, if any
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


# =========================================================
# SECTION 6: WATCHLIST MODELS
# =========================================================
class UserWatchlist(Base):
    __tablename__ = 'user_watchlists'
    __table_args__ = (UniqueConstraint('user_id', 'name', name='uq_watchlist_name_per_user'),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


class WatchlistItem(Base):
    __tablename__ = 'watchlist_items'
    __table_args__ = (UniqueConstraint('watchlist_id', 'ticker', name='uq_stock_once_per_watchlist'),)

    id = Column(Integer, primary_key=True)
    watchlist_id = Column(Integer, ForeignKey('user_watchlists.id', ondelete='CASCADE'), nullable=False)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    added_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


# =================================
# SECTION 7: TRADING SIGNALS MODEL
# =================================
class TradingSignal(Base):
    """What ONE strategy says about ONE stock on ONE day: BUY, SELL or HOLD."""
    __tablename__ = 'trading_signals'
    __table_args__ = (
        UniqueConstraint('ticker', 'strategy_id', 'signal_date', name='uq_signal_per_strategy_day'),
        CheckConstraint("signal_type IN ('BUY', 'SELL', 'HOLD')", name='ck_signal_type'),
        CheckConstraint('confidence_score BETWEEN 0 AND 1', name='ck_signal_confidence'),
        Index('ix_signals_date', 'signal_date'),               # "today's signals" is the common question
    )

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    signal_date = Column(String(10), nullable=False)           # the trading day it applies to
    signal_type = Column(String(10), nullable=False)           # 'BUY', 'SELL' or 'HOLD'
    confidence_score = Column(REAL, default=0.0, nullable=False)
    target_price = Column(REAL)
    model_name = Column(String(100))
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

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
    