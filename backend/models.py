# ========================
# Flask SQLAlchemy Models
# ========================
from datetime import datetime

from sqlalchemy import (
    REAL, TIMESTAMP, Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Parent of every table class. Columns are written as `name: Mapped[type] = mapped_column(...)`
    so editors and type checkers know a column holds a str, an int and so on, not a Column object."""

MARKET = "NASDAQ" # the app only covers this exchange

# =====================
# SECTION 1: USER MODEL
# =====================
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)  # never the password itself
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)  # filled in by the database
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1 = active, 0 = disabled



class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    experience_level: Mapped[str] = mapped_column(String(20), default="beginner", nullable=False)
    risk_comfort: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    signal_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    daily_summary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    strategy_updates: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class UserProfile(Base):
    __tablename__ = 'user_profiles'

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    goal: Mapped[str | None] = mapped_column(String(20))
    experience_level: Mapped[str | None] = mapped_column(String(20))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    sector: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)


# =======================
# SECTION 3: STOCK MODEL
# =======================
class Stock(Base):
    """One row per NASDAQ ticker we track. Other tables point at it by ticker."""
    __tablename__ = 'stocks'
    __table_args__ = (
        CheckConstraint(f"exchange_code = '{MARKET}'", name="ck_stocks_nasdaq_only"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey('companies.id'), nullable=False)
    exchange_code: Mapped[str] = mapped_column(String(10), default=MARKET, nullable=False)  # the market it trades on
    currency: Mapped[str] = mapped_column(String(3), default='USD', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # False = stop showing it
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False)    # 'YYYY-MM-DD' (text in this format sorts correctly)
    open: Mapped[float] = mapped_column(REAL, nullable=False)
    high: Mapped[float] = mapped_column(REAL, nullable=False)
    low: Mapped[float] = mapped_column(REAL, nullable=False)
    close: Mapped[float] = mapped_column(REAL, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    prediction_date: Mapped[str] = mapped_column(String(10), nullable=False)  # the day being predicted
    predicted_close: Mapped[float] = mapped_column(REAL, nullable=False)
    actual_close: Mapped[float | None] = mapped_column(REAL)  # filled in once the day is over
    confidence_score: Mapped[float] = mapped_column(REAL, default=0.0, nullable=False)  # 0 to 1
    direction: Mapped[str] = mapped_column(String(10), default='flat', nullable=False)  # expected price movement
    prediction_type: Mapped[str] = mapped_column(String(50), default='daily', nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default='baseline', nullable=False)  # e.g. 'xgboost', 'lstm'
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)


# ===========================
# SECTION 5B: STRATEGY MODEL
# ===========================
class Strategy(Base):
    """A named way of turning predictions and market trends into signals."""
    __tablename__ = 'strategies'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # e.g. 'Momentum'
    description: Mapped[str | None] = mapped_column(Text)  # plain-English explanation shown to users
    model_name: Mapped[str | None] = mapped_column(String(100))  # which model feeds it, if any
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)


# =========================================================
# SECTION 6: WATCHLIST MODELS
# =========================================================
class UserWatchlist(Base):
    __tablename__ = 'user_watchlists'
    __table_args__ = (UniqueConstraint('user_id', 'name', name='uq_watchlist_name_per_user'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)


class WatchlistItem(Base):
    __tablename__ = 'watchlist_items'
    __table_args__ = (UniqueConstraint('watchlist_id', 'ticker', name='uq_stock_once_per_watchlist'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(Integer, ForeignKey('user_watchlists.id', ondelete='CASCADE'), nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    added_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    strategy_id: Mapped[int] = mapped_column(Integer, ForeignKey('strategies.id'), nullable=False)
    signal_date: Mapped[str] = mapped_column(String(10), nullable=False)  # the trading day it applies to
    signal_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'BUY', 'SELL' or 'HOLD'
    confidence_score: Mapped[float] = mapped_column(REAL, default=0.0, nullable=False)
    target_price: Mapped[float | None] = mapped_column(REAL)
    model_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)

# ====================================
# SECTION 8: SIGNAL FLAGS & GUARDRAILS  
# ====================================

class SignalFlag(Base):
    __tablename__ = 'signal_flags'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(Integer, ForeignKey('trading_signals.id'), nullable=False)
    flag_type: Mapped[str] = mapped_column(String(50), nullable=False)  # Types of guardrails


class SignalReviewStatus(Base):
    __tablename__ = 'signal_review_status'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(Integer, ForeignKey('trading_signals.id'), nullable=False)
    review_state: Mapped[str] = mapped_column(String(50), nullable=False)  # Review level


class SignalOverride(Base):
    __tablename__ = 'signal_overrides'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(Integer, ForeignKey('trading_signals.id'), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    override_reason: Mapped[str | None] = mapped_column(Text)  # Why human made this decision
    original_signal: Mapped[str | None] = mapped_column(String(50), default='neutral')
    human_decision: Mapped[str] = mapped_column(String(20), nullable=False)  # Human's final decision
  