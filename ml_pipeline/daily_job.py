import json
import joblib
import numpy as np
import pandas as pd
import torch
import xgboost as xgb
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session

from .settings import engine, artifacts_path
from .alpaca import loadHistoricalData
from .features import build_features
from .model_def import LSTMModel

#==========================================================
# LOAD SAVED DATA FROM TRAIN
#==========================================================

config = json.loads((artifacts_path / "config.json").read_text())
future_predictions = config["future_predictions"]
lstm_features = config["lstm_features"]
sequence_len = config["sequence_len"]
typical_move = config["typical_move"]
version = config["version"]

model = xgb.XGBClassifier()
model.load_model(str(artifacts_path / "xgb_model.json"))

scaler = joblib.load(artifacts_path / "scaler.joblib")

dl_model = LSTMModel(input_dim=len(lstm_features), hidden_dim=config["hidden_dim"],
                     layer_dim=config["layer_dim"])
dl_model.load_state_dict(torch.load(artifacts_path / "lstm.pt"))
dl_model.eval()

#==========================================================
# GET LATEST DATA AND BUILD SAME FEATURES AS TRAINING
#==========================================================

# Get yesterday's bar + any missing new data

dfCloseFinal = loadHistoricalData()

dfCloseFinal = build_features(dfCloseFinal)
dfCloseFinal = dfCloseFinal.dropna(subset=future_predictions).copy()


dfCloseFinal["xgb_prob"] = model.predict_proba(dfCloseFinal[future_predictions])[:, 1]
dfCloseFinal["xgb_prob_raw"] = dfCloseFinal["xgb_prob"]
dfCloseFinal[lstm_features] = scaler.transform(dfCloseFinal[lstm_features])

latest = dfCloseFinal["date"].max()

syms = []
X = []
price = []
raw_prob = []

for sym, g in dfCloseFinal.groupby("symbol"):
    g = g.sort_values("date")
    if len(g) < sequence_len or g["date"].iloc[-1] != latest:
        continue
    syms.append(sym)
    X.append(g[lstm_features].tail(sequence_len).values)
    price.append(g["price"].iloc[-1])
    raw_prob.append(g["xgb_prob_raw"].iloc[-1])
    
with torch.no_grad():
    lstm_prob = torch.sigmoid(dl_model(torch.tensor(np.array(X), dtype=torch.float32))).numpy()
    
prediction_date = (latest + pd.offsets.BDay(1)).strftime("%Y-%m-%d")

#==========================================================
# SAVE OUT TO SQL DATABASE
#==========================================================

created_at = datetime.now(timezone.utc)

def build_export(model_name, probs):
    probs = np.asarray(probs)
    preds = (probs > 0.5).astype(int)
    px = np.asarray(price, dtype=float)
    return pd.DataFrame({
        "ticker" : syms,
        "prediction_date" : prediction_date,
        "predicted_close" : np.where(preds == 1, px * (1 + typical_move), px * (1 - typical_move)).round(2),
        "actual_close" : np.nan,
        "confidence_score" : np.where(preds == 1, probs, 1 - probs).round(4),
        "direction" : np.where(preds == 1, "up", "down"),
        "prediction_type" : "live",
        "model_name" : model_name,
        "created_at" : created_at,
    })
    
live_df = pd.concat([
    build_export(f"xgboost_{version}", raw_prob),
    build_export(f"xgboost_lstm_{version}", lstm_prob),
], ignore_index=True)

with engine.begin() as conn:
    conn.execute(text("""
        UPDATE predictions SET actual_close = (
            SELECT s.close FROM stock_data s
            WHERE s.ticker = predictions.ticker AND s.date = predictions.prediction_date)
        WHERE prediction_type = 'live' AND actual_close IS NULL
    """))
    
    existing = pd.read_sql(text(
        "SELECT ticker, prediction_date, model_name, 1 AS _hit FROM predictions"), conn )
    live_df = live_df.merge(existing, on=["ticker", "prediction_date", "model_name"], how="left")
    live_df = live_df[live_df["_hit"].isna()].drop(columns="_hit")
    
    live_df.to_sql("predictions", conn, if_exists="append", index=False)

    live_predictions = live_df.to_dict("records")

with Session(engine) as session:
    from backend.alerts import create_live_prediction_signals

    created_signals = create_live_prediction_signals(session, live_predictions)
    
print(f"Wrote {len(live_df)} live prediction rows to the predictions table for {prediction_date}")

print(live_df[["ticker", "prediction_date", "model_name", "direction", "confidence_score"]])