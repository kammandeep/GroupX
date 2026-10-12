-- =====================================================
-- STOCK PREDICTION DASHBOARD - SQLite Database Schema
-- =====================================================

-- Disable foreign keys check
PRAGMA foreign_keys = OFF;

-- =============================================
-- SECTION 1: USER AUTHENTICATION & MANAGEMENT
-- =============================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,           -- Login username
    email TEXT UNIQUE,                        -- Email for communication
    password_hash TEXT NOT NULL,              -- Hashed password
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1               -- 1 = active, 0 = inactive/deleted
);

-- =========================================
-- SECTION 2: STOCK COMPANIES INFORMATION
-- =========================================

CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,                  -- Stock symbol
    name TEXT NOT NULL,                       -- Company full name
    sector TEXT,                              -- Sector category
    industry TEXT,                            -- Industry sub-category
    exchange TEXT DEFAULT 'NYSE',             -- Stock exchange
    currency TEXT DEFAULT 'USD',              -- Default currency
    market_cap REAL,                          -- Market cap in base currency
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker)
);

-- ===========================================================================
-- SECTION 3: STOCK PRICE HISTORY (OHLCV - Open, High, Low, Close, Volume)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS stock_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,                     -- Foreign key to companies table
    date TEXT NOT NULL,                       -- Trading date in YYYY-MM-DD format
    open REAL NOT NULL,                       -- Opening price
    high REAL NOT NULL,                       -- Day's highest price
    low REAL NOT NULL,                        -- Day's lowest price
    close REAL NOT NULL,                      -- Closing price
    volume INTEGER DEFAULT 0,                 -- Trading volume (shares)
    
    CONSTRAINT fk_stock_data_company 
        FOREIGN KEY(ticker) REFERENCES companies(ticker) 
            ON DELETE CASCADE,
            
    UNIQUE(ticker, date)                      -- One record per ticker per date
);

-- ===========================================
-- SECTION 4: MODEL PREDICTIONS & RESULTS
-- ===========================================

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,                     -- Foreign key to companies table
    prediction_date TEXT NOT NULL,            -- Date model predicted for
    predicted_close REAL NOT NULL,             -- Predicted closing price
    actual_close REAL,                        -- Actual closing price (filled after market close)
    confidence_score REAL DEFAULT 0.0,        -- Model confidence (0-1)
    direction TEXT DEFAULT 'neutral',         -- 'buy', 'sell', 'hold'
    prediction_type TEXT DEFAULT 'daily',     -- 'daily', 'weekly', 'monthly'
    model_name TEXT DEFAULT 'baseline',       -- Which ML model made this
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_predictions_company 
        FOREIGN KEY(ticker) REFERENCES companies(ticker) 
            ON DELETE CASCADE,
            
    UNIQUE(ticker, prediction_date)           -- One prediction per ticker per date
);

-- =============================
-- SECTION 5: USER WATCHLISTS
-- =============================

CREATE TABLE IF NOT EXISTS user_watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,                 -- Foreign key to users table
    ticker TEXT NOT NULL,
    notes TEXT,                               -- User's notes about this stock
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_watchlist_user 
        FOREIGN KEY(user_id) REFERENCES users(id) 
            ON DELETE CASCADE,
            
    UNIQUE(user_id, ticker)                   -- No duplicate watches per user
);

-- ============================================
-- SECTION 6: BASIC INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_stock_data_date ON stock_data(date);
CREATE INDEX IF NOT EXISTS idx_predictions_ticker ON predictions(ticker);
CREATE INDEX IF NOT EXISTS idx_user_watchlists_user_id ON user_watchlists(user_id);

-- =============================================================================
-- SECTION 7: HELPER FUNCTIONS (VIEWS) FOR COMMON QUERIES
-- =============================================================================

-- View to get latest price for each stock
CREATE VIEW IF NOT EXISTS v_latest_prices AS
SELECT 
    ticker,
    date as latest_date,
    open, high, low, close, volume
FROM stock_data
WHERE date = (
    SELECT MAX(date)
    FROM stock_data s2
    WHERE s2.ticker = stock_data.ticker
);

-- View to get price change % for latest day
CREATE VIEW IF NOT EXISTS v_daily_changes AS
SELECT 
    ticker,
    close,
    ROUND(((close - lags_close.lag1) / lags_close.lag1) * 100, 2) as change_pct
FROM v_latest_prices
JOIN (
    SELECT 
        ticker,
        date,
        open, high, low, close, volume,
        LAG(close) OVER (PARTITION BY ticker ORDER BY date) as lag1
    FROM stock_data
) lags_close ON v_latest_prices.ticker = lags_close.ticker;

-- ================================================
-- DATABASE CONFIGURATION FOR BETTER PERFORMANCE
-- ================================================

PRAGMA journal_mode = WAL;                    -- Write-ahead logging for better concurrency
PRAGMA synchronous = NORMAL;                  -- Balance safety & performance
PRAGMA cache_size = -64000;                   -- 64MB cache (in pages, negative means KB)
PRAGMA temp_store = MEMORY;                   -- Use memory for temporary tables
PRAGMA foreign_keys = OFF;                    -- Keep off for SQLite simplicity



/*
TABLE SUMMARY:

1. users              → User accounts & authentication
2. companies          → Stock ticker information & metadata  
3. stock_data         → Daily OHLCV price data (one row per ticker per day)
4. predictions        → ML model predictions and results tracking
5. user_watchlists    → Per-user watchlist of tracked stocks

RELATIONSHIPS:

companies.id ←→ stock_data.ticker     → Stock data links to companies
users.id  ←→ user_watchlists.user_id  → Users own their watchlists
stock_data.date is YYYY-MM-DD text    → Use date strings, not timestamps

*/
