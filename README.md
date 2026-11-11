# GroupX

# Stock Predictions Dashboard

A Flask-based AI dashboard for NASDAQ stock forecasting using XGBoost and LSTM models.

## Run locally

Use Python 3.14 on Windows with the project virtual environment:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Flask serves both the pages and static assets; there
is no separate frontend development server. New accounts can be created at
`/signup`. The SQLite database is created at `instance/groupx.sqlite3`.
The runtime schema is defined by the SQLAlchemy models in `backend/models.py`;
`database/schema.sql` is not executed by the app.

To load sample stock data into that same database, run
`python -m database.seed_data` from the repository root.

TensorFlow is not installed on Python 3.14 for Windows because a compatible
stable wheel is unavailable. The Flask app does not import TensorFlow at startup.
