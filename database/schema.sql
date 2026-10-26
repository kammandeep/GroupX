-- ====================================================
-- STOCK PREDICTION DASHBOARD - SQLite Database Schema
-- ====================================================

-- SQLite default for development)
PRAGMA foreign_keys = OFF;

-- ============================================
-- SECTION 1: USER AUTHENTICATION & MANAGEMENT
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,            -- Login username
    email TEXT UNIQUE,                        -- Email for communication
    password_hash TEXT NOT NULL,              -- Hashed password
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1               -- 1 = active, 0 = inactive/deleted
);

-- ====================================================================
-- SECTION 2: STOCK COMPANIES INFORMATION (SPLIT INTO SEPARATE TABLES)
-- ====================================================================

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                       -- Company full name
    sector TEXT,                              -- Sector category (e.g., 'Technology', 'Finance')
    industry TEXT,                            -- Industry sub-category
    website TEXT,                             -- Company website
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- SECTION 3: STOCK TICKER INFORMATION WITH EXCHANGE MAPPING
-- ==========================================================

CREATE TABLE IF NOT EXISTS stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,              -- Stock symbol (e.g., 'AAPL', 'TSLA')
    company_id INTEGER NOT NULL,              -- FK to companies table
    exchange_code VARCHAR(10) DEFAULT 'NYSE', -- Stock exchange code
    currency TEXT DEFAULT 'USD',              -- Trading currency
    is_active BOOLEAN DEFAULT TRUE,           -- Market active/inactive status
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_stock_company 
        FOREIGN KEY(company_id) REFERENCES companies(id) 
            ON DELETE CASCADE
);

-- ========================================================================
-- SECTION 4: STOCK PRICE HISTORY (OHLCV - Open, High, Low, Close, Volume)
-- ========================================================================

CREATE TABLE IF NOT EXISTS stock_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,                     -- Foreign key to stocks table
    date TEXT NOT NULL,                       -- Trading date in YYYY-MM-DD format
    open REAL NOT NULL,                       -- Opening price
    high REAL NOT NULL,                       -- Day's highest price
    low REAL NOT NULL,                        -- Day's lowest price
    close REAL NOT NULL,                      -- Closing price
    volume INTEGER DEFAULT 0,                 -- Trading volume (shares)
    binary_label INTEGER DEFAULT 0,           -- Binary target: 1 = up (current > previous), 0 = down
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_stock_data_company 
        FOREIGN KEY(ticker) REFERENCES stocks(ticker) 
            ON DELETE CASCADE,
            
    UNIQUE(ticker, date)                      -- One record per ticker per date
);

-- ==================================================================
-- SECTION 5: MODEL PREDICTIONS & RESULTS (UPDATED WITH STOCK ID FK)
-- ==================================================================

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,                     -- Foreign key to stocks table
    prediction_date TEXT NOT NULL,            -- Date model predicted for
    predicted_close REAL NOT NULL,            -- Predicted closing price
    actual_close REAL,                        -- Actual closing price (filled after market close)
    confidence_score REAL DEFAULT 0.0,        -- Model confidence (0-1)
    direction TEXT DEFAULT 'neutral',         -- 'buy', 'sell', 'hold'
    prediction_type TEXT DEFAULT 'daily',     -- 'daily', 'weekly', 'monthly'
    model_name TEXT DEFAULT 'baseline',       -- Which ML model made this
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_predictions_company 
        FOREIGN KEY(ticker) REFERENCES stocks(ticker) 
            ON DELETE CASCADE,
            
    UNIQUE(ticker, prediction_date)           -- One prediction per ticker per date
);

-- =================================================================
-- SECTION 6: USER WATCHLISTS (NEW:Many-to-Many Relationship Added)
-- =================================================================

CREATE TABLE IF NOT EXISTS user_watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,                 -- Foreign key to users table
    name TEXT NOT NULL,                       -- Watchlist name (e.g., "Tech Portfolio")
    description TEXT,                         -- Optional notes about this watchlist
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_watchlist_user 
        FOREIGN KEY(user_id) REFERENCES users(id) 
            ON DELETE CASCADE,
            
    UNIQUE(name)                              -- Unique watchlist name per user
);

-- ========================================================================
-- SECTION 7: WATCHLIST STOCK ITEMS (NEW: Junction Table for Many-to-Many)
-- ========================================================================

CREATE TABLE IF NOT EXISTS watchlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL,            -- FK to user_watchlists
    ticker TEXT NOT NULL,                     -- Stock ticker (FK to stocks)
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_watchlist_item_user 
        FOREIGN KEY(watchlist_id) REFERENCES user_watchlists(id) 
            ON DELETE CASCADE,
            
    CONSTRAINT fk_watchlist_item_stock 
        FOREIGN KEY(ticker) REFERENCES stocks(ticker) 
            ON DELETE CASCADE,
            
    UNIQUE(watchlist_id, ticker)              -- No duplicate watches per watchlist
);

-- ===============================================================
-- SECTION 8: TRADING SIGNALS (FIXED incomplete Table Definition)
-- ===============================================================

CREATE TABLE IF NOT EXISTS trading_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,                     -- Stock ticker (FK to stocks table)
    signal_type VARCHAR(20) NOT NULL,         -- 'BUY', 'SELL', 'HOLD'
    confidence_score REAL DEFAULT 0.0,        -- Model/signal confidence (0-1)
    target_price REAL,                        -- Optional price target
    model_name TEXT,                          -- Which ML model generated this signal
    signal_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_signal_stock 
        FOREIGN KEY(ticker) References stocks(ticker) 
            ON DELETE CASCADE
);

-- =====================================
-- SECTION 9: HUMAN REVIEW & GUARDRAILS
-- =====================================

CREATE TABLE IF NOT EXISTS signal_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES trading_signals(id),
    flag_type TEXT NOT NULL,                  -- 'STALE_DATA', 'EARNINGS_UPCOMING', 
    'HIGH_VOLATILITY', 'MARKET_SHOCK', 'LOW_VOLUME'
    reason TEXT,                              -- Human-readable explanation of the flag
    
    CONSTRAINT chk_flag_type 
        CHECK(flag_type IN ('STALE_DATA', 'EARNINGS_UPCOMING', 
                           'HIGH_VOLATILITY', 'MARKET_SHOCK', 'LOW_VOLUME'))
);

CREATE TABLE IF NOT EXISTS signal_review_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES trading_signals(id),
    review_state TEXT NOT NULL,                -- 'CLEAR_SIGNAL', 'NEEDS_REVIEW'
    confidence_score REAL DEFAULT 0.0,         -- Signal confidence
    flagged BOOLEAN DEFAULT FALSE,             -- Whether guardrails triggered
    
    CONSTRAINT chk_review_state 
        CHECK(review_state IN ('CLEAR_SIGNAL', 'NEEDS_REVIEW', 'NO_CLEAR_SIGNAL', 'PAUSED'))
);

CREATE TABLE IF NOT EXISTS signal_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER REFERENCES trading_signals(id),
    user_id INTEGER REFERENCES users(id),
    override_reason TEXT,                      -- Why human made this decision
    original_signal TEXT DEFAULT 'neutral',    -- The AI's original signal
    human_decision TEXT NOT NULL,              -- Human's final decision ('BUY', 'SELL', 'HOLD')
    confidence_score REAL DEFAULT 0.0,         -- Human's confidence
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_human_decision 
        CHECK(human_decision IN ('BUY', 'SELL', 'HOLD'))
);

-- ========================================================================
-- SECTION 9: PREPROCESSED TRAINING DATA (XGBoost + Deep Learning Input)
-- ========================================================================

CREATE TABLE IF NOT EXISTS preprocessed_training_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,                     -- Foreign key to stocks table
    date TEXT NOT NULL,                       -- Training date in YYYY-MM-DD format
    X1 REAL NOT NULL,                         -- Input feature 1 (e.g., previous day close)
    X2 REAL NOT NULL,                         -- Input feature 2 (e.g., volume)
    X3 REAL NOT NULL,                         -- Input feature 3 (e.g., change %)
    XGBoost_predicted_close REAL,             -- XGBoost model prediction
    XGBoost_predicted_direction TEXT,         -- XGBoost binary prediction ('up'/'down')
    actual_close REAL,                        -- Actual closing price for validation
    deep_learning_input_flags INTEGER DEFAULT 0, -- Bitmask: bit 1=XGBoost used as DL training data
    
    CONSTRAINT fk_training_data_stock 
        FOREIGN KEY(ticker) References stocks(ticker) 
            ON DELETE CASCADE,
            
    UNIQUE(ticker, date)                      -- One record per ticker per date
);

-- =========================================================
-- SECTION 10: PORTFOLIO SELECTION TYPES (Top/Mid/Bottom 5)
-- =========================================================

CREATE TABLE IF NOT EXISTS portfolio_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,                -- 'top5', 'mid5', 'bottom5'
    description TEXT,                         -- Description of the portfolio type
    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_portfolio_type_name 
        CHECK(name IN ('top5', 'mid5', 'bottom5'))
);

-- =================================================================
-- SECTION 10: PORTFOLIO SELECTION TABLES (Top/Mid/Bottom 5 Stocks)
-- =================================================================

CREATE TABLE IF NOT EXISTS portfolio_top_5 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_type TEXT NOT NULL REFERENCES portfolio_types(id),
    ticker TEXT NOT NULL UNIQUE,              -- Stock ticker in this portfolio
    entry_price REAL,                         -- Entry price for tracking P&L
    entry_date TEXT,                          -- Date of entry
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolio_mid_5 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_type TEXT NOT NULL REFERENCES portfolio_types(id),
    ticker TEXT NOT NULL UNIQUE,              -- Stock ticker in this portfolio
    entry_price REAL,                         -- Entry price for tracking P&L
    entry_date TEXT,                          -- Date of entry
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolio_bottom_5 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_type TEXT NOT NULL REFERENCES portfolio_types(id),
    ticker TEXT NOT NULL UNIQUE,              -- Stock ticker in this portfolio
    entry_price REAL,                         -- Entry price for tracking P&L
    entry_date TEXT,                          -- Date of entry
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================
-- SECTION 9: BASIC INDEXES FOR PERFORMANCE
-- =========================================

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_stock_data_date ON stock_data(date);
CREATE INDEX IF NOT EXISTS idx_predictions_ticker ON predictions(ticker);
CREATE INDEX IF NOT EXISTS idx_user_watchlists_user_id ON user_watchlists(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_items_watchlist ON watchlist_items(watchlist_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_items_stock ON watchlist_items(ticker);

-- New indexes for ML pipeline tables
CREATE INDEX IF NOT EXISTS idx_training_data_ticker ON preprocessed_training_data(ticker);
CREATE INDEX IF NOT EXISTS idx_training_data_date ON preprocessed_training_data(date);

-- ===========================================
-- SECTION 10: HELPER VIEWS FOR QUICK QUERIES
-- ===========================================

-- View to get latest price for each stock
CREATE VIEW IF NOT EXISTS v_latest_prices AS
SELECT 
    sd.id,
    sd.ticker,
    sd.date as latest_date,
    sd.open, sd.high, sd.low, sd.close, sd.volume,
    c.name as company_name,
    s.exchange_code
FROM stock_data sd
INNER JOIN stocks s ON s.ticker = sd.ticker
INNER JOIN companies c ON c.id = s.company_id
WHERE sd.date = (
    SELECT MAX(date)
    FROM stock_data s2
    WHERE s2.ticker = sd.ticker
);

-- View to get price change % for latest day
CREATE VIEW IF NOT EXISTS v_daily_changes AS
SELECT 
    ticker,
    close,
    ROUND(((close - lags_close.lag1) / NULLIF(lags_close.lag1, 0)) * 100, 2) as change_pct
FROM v_latest_prices
JOIN (
    SELECT 
        ticker,
        date,
        open, high, low, close, volume,
        LAG(close) OVER (PARTITION BY ticker ORDER BY date) as lag1
    FROM stock_data
) lags_close ON v_latest_prices.ticker = lags_close.ticker;

-- View to get user's watchlist stocks
CREATE VIEW IF NOT EXISTS v_user_watchlist AS
SELECT 
    u.id as user_id,
    w.name as watchlist_name,
    st.ticker,
    c.name as company_name,
    st.close as latest_price,
    sd.date as latest_date
FROM user_watchlists w
JOIN users u ON u.id = w.user_id
JOIN watchlist_items wi ON wi.watchlist_id = w.id
JOIN stocks st ON st.ticker = wi.ticker
LEFT JOIN companies c ON c.id = st.company_id
LEFT JOIN stock_data sd ON sd.ticker = st.ticker AND sd.date = (
    SELECT MAX(date) FROM stock_data WHERE ticker = st.ticker
);

-- View to get recent trading signals
CREATE VIEW IF NOT EXISTS v_recent_signals AS
SELECT 
    ts.id,
    ts.ticker,
    c.name as company_name,
    ts.signal_type,
    ts.confidence_score,
    ts.target_price,
    ts.model_name,
    ts.signal_timestamp
FROM trading_signals ts
JOIN stocks st ON st.ticker = ts.ticker
JOIN companies c ON c.id = st.company_id
ORDER BY ts.signal_timestamp DESC;

-- ==============================================
-- DATABASE CONFIGURATION FOR BETTER PERFORMANCE
-- ==============================================

PRAGMA journal_mode = WAL;                    -- Write-ahead logging for better concurrency
PRAGMA synchronous = NORMAL;                  -- Balance safety & performance
PRAGMA cache_size = -64000;                   -- 64MB cache (in pages, negative means KB)
PRAGMA temp_store = MEMORY;                   -- Use memory for temporary tables

-- =============================================
-- USAGE NOTES (For your development reference)
-- =============================================

/*
TABLE SUMMARY:

1. users              → User accounts & authentication
2. companies          → Stock company information 
3. stocks             → Stock ticker + exchange mappings  
4. stock_data         → Daily OHLCV price data (one row per ticker per day)
5. predictions        → ML model predictions and results tracking
6. user_watchlists    → User watchlist containers with names/descriptions
7. watchlist_items    → Junction table: Many-to-Many between watchlists and stocks
8. trading_signals    → Trading signals with confidence scores

RELATIONSHIPS:

users.id  ←→ user_watchlists.user_id   → Users own their watchlists
user_watchlists.id ←→ watchlist_items.watchlist_id → Watchlists contain items  
stocks.ticker ←→ watchlist_items.ticker → Watchlist items map to stocks
companies.id ←→ stocks.company_id      → Stocks link to companies