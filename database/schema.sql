-- ============================================================
-- STOCK FORECASTING DASHBOARD - SQLITE DATABASE SCHEMA
-- ============================================================
-- Description: Production-ready database for ML stock predictions with user management, portfolio tracking, and alerts.
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ----------------------------------------------------------------------
-- CORE STOCK MARKET DATA TABLES
-- ----------------------------------------------------------------------

-- Table: exchanges
-- Purpose: Store exchange information (NYSE, NASDAQ, etc.)
CREATE TABLE IF NOT EXISTS exchanges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(10) NOT NULL UNIQUE,
    country VARCHAR(50),
    timezone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: companies
-- Purpose: Store company information and sector/industry classification
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(100),
    industry VARCHAR(100),
    description TEXT,
    website VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: stocks
-- Purpose: Store stock ticker information with exchange mapping
-- This is the CENTRAL TABLE that everything else connects to!
CREATE TABLE IF NOT EXISTS stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    company_id INTEGER,
    exchange_id INTEGER NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL,
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id) ON DELETE CASCADE
    
    -- Performance Indexes
);

CREATE INDEX idx_stocks_ticker ON stocks(ticker);
CREATE INDEX idx_stocks_company ON stocks(company_id);
CREATE INDEX idx_stocks_exchange ON stocks(exchange_id);
CREATE INDEX idx_stocks_active ON stocks(is_active);

-- Table: daily_prices
-- Purpose: Store daily OHLCV (Open, High, Low, Close, Volume) data
CREATE TABLE IF NOT EXISTS daily_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(18, 4),
    high DECIMAL(18, 4),
    low DECIMAL(18, 4),
    close DECIMAL(18, 4),
    volume BIGINT,
    
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
    
    -- Composite Unique Constraint to prevent duplicate dates per stock
    UNIQUE(stock_id, date)
);

-- Performance Index for time-series queries
CREATE INDEX idx_daily_prices_stock_date ON daily_prices(stock_id, date DESC);
CREATE INDEX idx_daily_prices_date ON daily_prices(date);

-- Table: financial_ratios
-- Purpose: Store computed valuation metrics (P/E, P/B, etc.)
CREATE TABLE IF NOT EXISTS financial_ratios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    calculation_date DATE NOT NULL,
    pe_ratio DECIMAL(10, 2),
    pb_ratio DECIMAL(10, 2),
    debt_to_equity DECIMAL(10, 4),
    roe DECIMAL(10, 4),
    ps_ratio DECIMAL(10, 4),
    
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
    
    -- Unique constraint to store latest values per stock
    UNIQUE(stock_id, calculation_date)
);

-- ----------------------------------------------------------------------
-- USER MANAGEMENT TABLES
-- ----------------------------------------------------------------------

-- Table: users
-- Purpose: Store user account information with hashed passwords
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Index for email lookups
    INDEX idx_users_email (email)
);

-- Table: watchlists
-- Purpose: User-defined stock watchlists (e.g., "My Portfolio", "Tech Stocks")
CREATE TABLE IF NOT EXISTS watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    
    -- Index for user lookups
    INDEX idx_watchlists_user (user_id)
);

-- Table: watchlist_items
-- Purpose: Map stocks to watchlists (Many-to-Many relationship)
CREATE TABLE IF NOT EXISTS watchlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (watchlist_id) REFERENCES watchlists(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
    
    -- Composite Unique Constraint to prevent duplicate mappings
    UNIQUE(watchlist_id, stock_id)
);

-- Table: portfolios
-- Purpose: User portfolio containers with custom names
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- Index for user lookups
    INDEX idx_portfolios_user (user_id)
);

-- Table: portfolio_holdings
-- Purpose: Track individual stock holdings within portfolios
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    quantity DECIMAL(18, 6) NOT NULL DEFAULT 0.0,
    purchase_price DECIMAL(18, 4),
    purchase_date DATE,
    
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
    
    -- Composite Unique Constraint to track per stock per portfolio
    UNIQUE(portfolio_id, stock_id)
);

CREATE INDEX idx_portfolio_holdings_stock ON portfolio_holdings(stock_id);
CREATE INDEX idx_portfolio_holdings_user ON portfolio_holdings(portfolio_id);

-- ----------------------------------------------------------------------
-- PREDICTION & MODEL TRACKING TABLES
-- ----------------------------------------------------------------------

-- Table: ml_models
-- Purpose: Store information about ML models (XGBoost, LSTM, SVC, etc.)
CREATE TABLE IF NOT EXISTS ml_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    algorithm_type VARCHAR(100),
    parameters_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    
    -- Index for algorithm type queries
);

CREATE INDEX idx_ml_models_algorithm ON ml_models(algorithm_type);

-- Table: model_versions
-- Purpose: Track different versions of a model with performance metrics
CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    version_string VARCHAR(50) NOT NULL,
    trained_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accuracy_score DECIMAL(10, 6),
    mape DECIMAL(10, 4),
    
    FOREIGN KEY (model_id) REFERENCES ml_models(id) ON DELETE CASCADE
    
    -- Unique constraint to allow multiple versions per model
);

CREATE INDEX idx_model_versions_model ON model_versions(model_id);
CREATE INDEX idx_model_versions_accuracy ON model_versions(accuracy_score DESC);

-- Table: predictions
-- Purpose: Store ML model prediction outputs with confidence intervals
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    target_date DATE NOT NULL,
    predicted_price DECIMAL(18, 4),
    lower_bound DECIMAL(18, 4),
    upper_bound DECIMAL(18, 4),
    prediction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
    
    -- Composite Unique to prevent duplicate predictions per target date
    UNIQUE(model_version_id, stock_id, target_date)
);

CREATE INDEX idx_predictions_stock_date ON predictions(stock_id, target_date DESC);
CREATE INDEX idx_predictions_model ON predictions(model_version_id);

-- Table: prediction_evaluations
-- Purpose: Track actual vs. predicted performance (for model validation)
CREATE TABLE IF NOT EXISTS prediction_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL,
    actual_price DECIMAL(18, 4),
    absolute_error DECIMAL(18, 4),
    squared_error DECIMAL(18, 6),
    
    FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE
    
    -- Unique constraint for evaluation per prediction
);

CREATE INDEX idx_evaluations_prediction ON prediction_evaluations(prediction_id);

-- ----------------------------------------------------------------------
-- TRADING SIGNALS & ALERTS TABLES
--------------------------------------------------------------------

-- Table: trading_signals
-- Purpose: Store buy/sell signals generated by models or other sources
CREATE TABLE IF NOT EXISTS trading_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    model_version_id INTEGER,
    signal_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    signal_type VARCHAR(50) NOT NULL,  -- 'BUY', 'SELL', 'HOLD'
    confidence DECIMAL(5, 4),
    action_price DECIMAL(18, 4),
    
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id) ON DELETE SET NULL
    
    -- Index for recent signals
);

CREATE INDEX idx_trading_signals_stock_time ON trading_signals(stock_id, signal_timestamp DESC);
CREATE INDEX idx_trading_signals_type ON trading_signals(signal_type);

-- Table: user_alerts
-- Purpose: User-defined price alerts (e.g., "Alert me when AAPL > $150")
CREATE TABLE IF NOT EXISTS user_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    alert_type VARCHAR(50) NOT NULL,  -- 'PRICE_TARGET', 'PERCENTAGE_CHANGE'
    target_value DECIMAL(18, 4),
    threshold_type VARCHAR(20) DEFAULT 'above',  -- 'above', 'below'
    is_active BOOLEAN DEFAULT TRUE,
    notification_method VARCHAR(50) DEFAULT 'email',
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
    
    -- Index for active alerts
);

CREATE INDEX idx_user_alerts_user_stock ON user_alerts(user_id, stock_id);
CREATE INDEX idx_user_alerts_active ON user_alerts(is_active);

-- Table: alert_history
-- Purpose: Log when alerts have been triggered
CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER NOT NULL,
    triggered_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trigger_value DECIMAL(18, 4),
    
    FOREIGN KEY (alert_id) REFERENCES user_alerts(id) ON DELETE CASCADE
    
    -- Index for recent triggers
);

CREATE INDEX idx_alert_history_trigger ON alert_history(triggered_timestamp DESC);

