import pandas as pd
import numpy as np
import copy
import joblib
import json
from dotenv import load_dotenv
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from pathlib import Path

from .settings import engine, artifacts_path, symbol_map, symbol_map_reverse
from .alpaca import loadHistoricalData
from .features import build_features, future_predictions
from .model_def import LSTMModel


version = "v1" # 1st version of this split from the original model.py

torch.manual_seed(42)
np.random.seed(42)

#======================================================
# PRE-PROCESSING FOR ML - XGBOOST
#======================================================

dfCloseFinal = loadHistoricalData()
print(dfCloseFinal.shape)
print(dfCloseFinal.isnull().sum())
print(dfCloseFinal.duplicated(subset=["symbol", "date"]).sum())

dfCloseFinal = build_features(dfCloseFinal)

print(dfCloseFinal['day_price_diff'].isna().sum())
print(dfCloseFinal['day_percentage_change'].isna().sum())

print(dfCloseFinal.sort_values('day_percentage_change', ascending=True).head(20))

print(dfCloseFinal.sort_values('day_percentage_change', ascending=False).head(20))

#======================================================
# SET THE INPUTS
#======================================================

# MAP THE SYMBOLS SO NO ERRORS OCCUR LATER IN THE PREDICTION PROCESS
dfCloseFinal['symbol'] = dfCloseFinal['symbol'].map({'AAPL': 0, 'AMZN' : 1,'GOOGL': 2, 'MSFT': 3, 'NVDA': 4})

dfCloseFinal['next_day'] = dfCloseFinal.groupby('symbol')['price'].shift(-1)
dfCloseFinal['next_date'] = dfCloseFinal.groupby('symbol')['date'].shift(-1)

dfCloseFinal = dfCloseFinal.dropna(subset=['next_day']).copy()

dfCloseFinal['target_day'] = (dfCloseFinal['next_day'] > dfCloseFinal['price']).astype(int)

dfCloseFinal = dfCloseFinal.dropna(subset= future_predictions + ['target_day']).copy()

break_date_1 = pd.Timestamp("2023-10-20")
break_date_2 = pd.Timestamp("2025-04-20")

train_model = dfCloseFinal[dfCloseFinal['date'] <= break_date_1].copy()
validate_model = dfCloseFinal[(dfCloseFinal['date'] > break_date_1) & (dfCloseFinal['date'] <= break_date_2)].copy()
test_model = dfCloseFinal[dfCloseFinal['date'] > break_date_2].copy()

X_train, y_train = train_model[future_predictions], train_model['target_day']
X_val, y_val = validate_model[future_predictions], validate_model['target_day']
X_test, y_test = test_model[future_predictions], test_model['target_day']

print(dfCloseFinal[dfCloseFinal['symbol'] == 0][['date', 'price', 'next_day', 'target_day']].head(10))
print(y_train.value_counts(normalize=True))
print(y_val.value_counts(normalize=True))
print(y_test.value_counts(normalize=True))
print(X_train.shape, X_val.shape, X_test.shape)

typical_move = float(train_model['day_percentage_change'].abs().median() / 100)

#======================================================
# SET TRAIN AND TEST THE ML MODEL - XGBOOST
#======================================================

model = xgb.XGBClassifier(booster="gbtree", n_estimators=200, max_depth=4, learning_rate=0.1)

model.fit(X_train, y_train, eval_set=[(X_val, y_val)])

y_pred = model.predict(X_val)

# Use predict_proba for the lstm model later
val_proba = model.predict_proba(X_val)[:,1]
test_proba = model.predict_proba(X_test)[:,1]

# FOR INTERNAL USE ONLY TO ENSURE PREDICTIONS ARE COMING THROUGH
print("Accuracy: ", accuracy_score(y_val, y_pred))
print("AUC: ", roc_auc_score(y_val, val_proba))
print("\nClassification:\n", classification_report(y_val, y_pred))

# SET UP NEW DATAFRAMES WITH EVALUATION AND TEST RESULTS
validate_model['xgb_prob'] = val_proba
test_model['xgb_prob'] = test_proba

# SAVE OUT EVALUATION AND TEST PREDICTIONS TO CSV FILES
keep = ['symbol', 'date', 'price', 'next_day', 'next_date'] + future_predictions + ['xgb_prob', 'target_day']

#======================================================
# SET, TRAIN AND TEST THE DL MODEL - LSTM
#======================================================

val_df = validate_model[keep]
test_df = test_model[keep]

# SET THE FEATURES / INPUTS FOR THE LSTM MODEL
lstm_features = future_predictions + ['xgb_prob']
sequence_len = 20
target = 'target_day'

val_dates = np.sort(val_df['date'].unique())
cut = val_dates[int(len(val_dates) * 0.7)]
val_end = val_dates[-1]

lstm_train_rows = val_df[val_df['date'] <= cut ]
scaler = StandardScaler().fit(lstm_train_rows[lstm_features])

all_df = pd.concat([val_df, test_df], ignore_index=True)
all_df = all_df.sort_values(['symbol', 'date']).reset_index(drop=True)
all_df['xgb_prob_raw'] = all_df['xgb_prob']
all_df[lstm_features] = scaler.transform(all_df[lstm_features])

# FUNCTION TO SET THE X, Y DATES, XGBOOST PREDICTIONS (PROBA) AND SYMS (STOCK SYMBOLS)
def make_sequences(df, features, target, sequence_len, start=None, end=None):
    X = []
    y = []
    d = []
    raw_prob = []
    syms = []
    price = []
    next_close = []
    next_date = []
    for sym, g in df.groupby('symbol'):
        g = g.sort_values('date')
        f = g[features].values
        t = g[target].values
        p = g['xgb_prob_raw'].values
        dates = g['date'].values
        prc = g['price'].values
        nc = g['next_day'].values
        nd = g['next_date'].values
        for i in range(sequence_len - 1, len(g)):
            if start is not None and dates[i] <= start:
                continue
            if end is not None and dates[i] > end:
                continue
            X.append(f[i - sequence_len + 1 : i + 1])
            y.append(t[i])
            d.append(dates[i])
            syms.append(sym)
            raw_prob.append(p[i])
            price.append(prc[i])
            next_close.append(nc[i])
            next_date.append(nd[i])
    return {
        "X": np.array(X),
        "y": np.array(y),
        "raw_prob": np.array(raw_prob),
        "dates":np.array(d),
        "syms":np.array(syms),
        "price":np.array(price),
        "next_close":np.array(next_close),
        "next_date":np.array(next_date),
    }
    
dl_train = make_sequences(all_df, lstm_features, target, sequence_len, end=cut)
dl_val = make_sequences(all_df, lstm_features, target, sequence_len, start=cut, end=val_end)
dl_test = make_sequences(all_df, lstm_features, target, sequence_len, start=val_end)

# CONVERT THE DATA USING PYTORCH SO LSTM CAN USE SAID DATA THROUGH FUNCTION
def to_tensor(X, y):
    return(torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32))

X_train_tensor, y_train_tensor = to_tensor(dl_train["X"], dl_train["y"])
X_val_tensor, y_val_tensor = to_tensor(dl_val["X"], dl_val["y"])
X_test_tensor, y_test_tensor = to_tensor(dl_test["X"], dl_test["y"])

train_loader = DataLoader(TensorDataset(X_train_tensor, y_train_tensor), batch_size=64, shuffle=True) 

#======================================================
# SET THE DL MODEL - LSTM
#======================================================

hidden_dim = 100
layer_dim = 1

dl_model = LSTMModel(input_dim=len(lstm_features), hidden_dim=hidden_dim, layer_dim=layer_dim)
criterion = nn.BCEWithLogitsLoss()
optimiser = torch.optim.Adam(dl_model.parameters(), lr=0.001, weight_decay=1e-4)

num_epochs = 200
patience = 10
best_val_loss = float("inf")
best_state = None
no_epoch_improvemnt = 0

for epoch in range(num_epochs):
    dl_model.train()
    for xb, yb in train_loader:
        optimiser.zero_grad()
        loss = criterion(dl_model(xb), yb)
        loss.backward()
        optimiser.step()
        
    dl_model.eval()
    with torch.no_grad():
        val_loss = criterion(dl_model(X_val_tensor), y_val_tensor).item()
    
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        best_state = copy.deepcopy(dl_model.state_dict())
        no_epoch_improvemnt = 0
    else:
        no_epoch_improvemnt += 1
        
    if (epoch + 1) % 10 == 0:
        print(f"Epoch [{epoch+1}/{num_epochs}], Loss: {loss.item():.4f}")
        
    if no_epoch_improvemnt >= patience:
        break
    
dl_model.load_state_dict(best_state)

dl_model.eval()

with torch.no_grad():
    test_prob = torch.sigmoid(dl_model(X_test_tensor)).numpy()
    
majority_class = int(round(dl_train["y"].mean()))
majority_acc = accuracy_score(dl_test["y"], np.full_like(dl_test["y"], majority_class))
print("Test Accuracy xgboost:", accuracy_score(dl_test["y"], (dl_test["raw_prob"] > 0.5).astype(int)))
print("Test Accuracy xgboost + lstm:", accuracy_score(dl_test["y"], (test_prob > 0.5).astype(int)))
print("Test Accuracy majority class:", majority_acc)
print("Test AUC xgboost:", roc_auc_score(dl_test["y"], dl_test["raw_prob"]))
print("Test AUC xgboost + lstm:", roc_auc_score(dl_test["y"], test_prob))

#======================================================
# SAVE OUT FOR DAILY JOB
#======================================================

artifacts_path.mkdir(parents=True, exist_ok=True)

model.save_model(str(artifacts_path / "xgb_model.json"))
torch.save(best_state, artifacts_path / "lstm.pt")
joblib.dump(scaler, artifacts_path / "scaler.joblib")

(artifacts_path / "config.json").write_text(json.dumps({
    "version":version,
    "future_predictions": future_predictions,
    "lstm_features":lstm_features,
    "sequence_len": sequence_len,
    "hidden_dim":hidden_dim,
    "layer_dim":layer_dim,
    "typical_move": typical_move,
}, indent=2))

print("Saved model files to", artifacts_path)

#==========================================================
# TO SQL DATABASE SECTION
#==========================================================

created_at = datetime.now(timezone.utc)

def build_export(model_name, probs):
    preds = (probs >0.5).astype(int)
    price = dl_test['price']
    return pd.DataFrame({
        "ticker" : pd.Series(dl_test["syms"]).map(symbol_map_reverse).values,
        "prediction_date" : pd.to_datetime(dl_test["next_date"]).strftime("%Y-%m-%d"),
        "predicted_close" : np.where(preds == 1, price * (1 + typical_move), price *(1 - typical_move)).round(2),
        "actual_close" : dl_test['next_close'].round(2),
        "confidence_score" : np.where(preds == 1, probs, 1 - probs).round(4),
        "direction" : np.where(preds == 1, "up", "down"),
        "prediction_type" : "backtest",
        "model_name" : model_name,
        "created_at" : created_at,
    })
    
xgb_name = f"xgboost_{version}"
lstm_name = f"xgboost_lstm_{version}"

export_df = pd.concat([
    build_export(xgb_name, dl_test['raw_prob']),
    build_export(lstm_name, test_prob),
], ignore_index=True)

export_df = export_df.sort_values(["prediction_date", "ticker", "model_name"]).reset_index(drop=True)

with engine.begin() as conn:
    
    conn.execute(
        text(
            "DELETE FROM predictions WHERE prediction_type = 'backtest' "
            "AND model_name IN (:a, :b)"
        ), {"a" : xgb_name, "b" : lstm_name},
    )
    
    existing = pd.read_sql(text("SELECT ticker, prediction_date, model_name, 1 AS _hit FROM predictions"), conn)
    export_df = export_df.merge(existing, on=['ticker', "prediction_date", "model_name"], how="left")
    export_df = export_df[export_df["_hit"].isna()].drop(columns="_hit")
    
    export_df.to_sql("predictions", conn, if_exists="append", index=False, chunksize=1000)
    
print(dfCloseFinal.groupby("symbol")["date"].agg(["min", "max", "count"]))

print(f"Wrote {len(export_df)} rows to the prediction table")