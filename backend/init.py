# ==============================
# Backend Package Initialization
# ==============================
"""
Re-exports all model classes and backend functionality.
"""

# Import Flask app and helper functions first
from . import app as backend_app  # Imports app.py's contents

# Import all models
from .models import (
    User, UserSettings, AlertRule, AlertEvent, Company, Stock, StockData, Prediction,
    UserWatchlist, WatchlistItem, TradingSignal, SignalFlag,
    SignalReviewStatus, SignalOverride
)

__all__ = [
    'app', 'init_db', 'get_latest_close',  # Flask app and helper functions
    'User', 'UserSettings', 'AlertRule', 'AlertEvent', 'Company', 'Stock', 'StockData', 'Prediction',
    'UserWatchlist', 'WatchlistItem', 'TradingSignal', 
    'SignalFlag', 'SignalReviewStatus', 'SignalOverride'  # Model classes
]