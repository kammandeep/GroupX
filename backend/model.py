import pandas as pd
import numpy as np
import copy
from dotenv import load_dotenv
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import requests
import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
import uuid
from pathlib import Path

load_dotenv()

#==============================================
# API TO GRAB HISTORICAL DATA
#==============================================

# Get locally stored API Keys from .evn file
keyID = os.getenv("APCA_API_KEY_ID")
secretKeyID = os.getenv("APCA_API_SECRET_KEY")

# print if successful
print(keyID is not None, secretKeyID is not None)

# set headers for the API call
headers = {
            "accept": "application/json",
            "APCA-API-KEY-ID": keyID,
            "APCA-API-SECRET-KEY": secretKeyID,
        }

# Function to set timeouts and report back on errors
def UniversalTry(url):
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return(response)
    except requests.exceptions.Timeout:
        print("The request timed out. THe server took too long to respond")
        exit()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error {e}")
        exit()
    except requests.exceptions.RequestException as e:
        print(f"Something has gone horribly wrong {e}")
        exit()

db_path = Path(__file__).parent.parent / "instance" / "groupx.sqlite3"
print("GroupX/instance ", db_path, db_path.exists())
assert db_path.exists(), f"Database not found at {db_path}"

engine = create_engine(f"sqlite:///{db_path.as_posix()}")    
    
# Call to grab historical data from the past 10 years for top 5 companies
def fetchHistoricalData():
    print("Getting Historical Data")
    url = "https://data.alpaca.markets/v2/stocks/bars?symbols=AAPL%2CAMZN%2CGOOGL%2CMSFT%2CNVDA&timeframe=1D&start=2016-11-15T01%3A02%3A03.123456789Z&limit=1000&adjustment=raw&feed=sip&sort=asc"
    rows = []
    token = ""
    
    while True:
        if token != "":
            updatedUrl = f"{url}&page_token={token}"
        else:
            updatedUrl = url
        data = UniversalTry(updatedUrl).json()
        
        for symbol, bars in (data.get("bars") or {}).items():
            for b in bars:
                rows.append({
                            "symbol":symbol,
                            "date":b["t"][:10],
                            "open": b["o"],
                            "high": b["h"],
                            "low": b["l"],
                            "close": b["c"],
                            "volume":b["v"]
                            })
        token = data.get("next_page_token")
        if not token:
            break
    return pd.DataFrame(rows)

# Function to check if the CSV exists and to create a new one if not
def checkCSV():
    if not os.path.exists("Historicalbars.csv"):
        print("No file exists by this name, creating now")
        df = fetchHistoricalData()
        df.to_csv("Historicalbars.csv", index=False)

checkCSV()
df = pd.read_csv("Historicalbars.csv")


print(df.isnull().sum())


print(df.info())
print(df.describe())
print("Missing Values: ")
print(df.isnull().sum())
print("Duplicates: ")
print(df.index.duplicated().sum())

#======================================================
# SAVING TO SQL DB
#======================================================

# create sql columns and ready db to be saved to sql database
def build_daily(df):
    dfOut = df.rename(columns={"symbol": "ticker"}).copy()
    
    dfOut["created_at"] = datetime.now(timezone.utc)
    dfOut["date"] = pd.to_datetime(dfOut["date"]).dt.date
    return dfOut[["ticker", "date", "open", "high", "low", "close", "volume", "created_at"]]

def loadHistoricalData():
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM stock_data")).scalar()
        
    if count == 0:
        print("stock_data is empty, downloading new set")
        daily = build_daily(fetchHistoricalData())
        daily.to_sql("stock_data", engine, if_exists="append", index=False, chunksize=1000)
        
    return pd.read_sql(
        text("SELECT ticker AS symbol, date, close AS price "
             "FROM stock_data ORDER BY ticker, date"), engine, parse_dates=["date"]
    )



#======================================================
# PRE-PROCESSING FOR ML - XGBOOST
#======================================================

dfCloseFinal = loadHistoricalData()
print(dfCloseFinal.shape)
print(dfCloseFinal.isnull().sum)
print(dfCloseFinal.duplicated(subset=["symbol", "date"]).sum())


dfCloseFinal = dfCloseFinal.sort_values(["symbol", "date"]).reset_index(drop=True)

#======================================================
# CALCULATE THE TARGET - DAYS
#======================================================


dfCloseFinal['price_raw'] = dfCloseFinal['price']

splits = [
    ('AAPL', '2020-08-31', 4),
    ('NVDA', '2021-07-20', 4),
    ('NVDA', '2024-06-10', 10),
    ('AMZN', '2022-06-06', 20),
    ('GOOGL', '2022-07-18', 20)
]

dfCloseFinal['split_factor'] = 1.0

for symbol, split_date, ratio in splits:
    mask = (dfCloseFinal['symbol'] == symbol) & (dfCloseFinal['date'] < pd.Timestamp(split_date))
    dfCloseFinal.loc[mask, 'split_factor'] *= ratio
    
dfCloseFinal['price'] = dfCloseFinal['price_raw'] / dfCloseFinal['split_factor']

# calculate the difference of the current and previous row for each row in the symbol group
dfCloseFinal['day_price_diff'] = dfCloseFinal.groupby('symbol')['price'].diff()


# calculate the percentage of the current and previous row for each row in the symbol group
dfCloseFinal['day_percentage_change'] = dfCloseFinal.groupby('symbol')['price'].pct_change() * 100


# ensure there are no more NaN values
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

dfCloseFinal['up_day'] = (dfCloseFinal['day_percentage_change'] > 0).astype(int)

horizons = [2, 5, 50, 250]
future_predictions = []

for horizon in horizons:
    ratio_col = f"Close_Ratio_{horizon}"
    trend_col = f"Trend_{horizon}"
    vol_col = f"Volatility_{horizon}"
    
    rolling_avg = (dfCloseFinal.groupby('symbol')['price'].rolling(horizon).mean().reset_index(level=0, drop=True))
    
    dfCloseFinal[f"Close_Ratio_{horizon}"] = dfCloseFinal['price'] / rolling_avg
    
    dfCloseFinal[f"Trend_{horizon}"] = (dfCloseFinal.groupby('symbol')['up_day'].rolling(horizon).sum().reset_index(level=0, drop=True))
    
    dfCloseFinal[f"Volatility_{horizon}"] = (dfCloseFinal.groupby('symbol')['day_percentage_change'].rolling(horizon).std().reset_index(level=0, drop=True))
    
    future_predictions += [ratio_col, trend_col, vol_col]

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

# SET CLASS WITH OWN FUNCTIONS TO BE CALLED LATER
class LSTMModel(nn.Module):
    # SETS THE DIMENSIONS TO BE USED IN THE LSTM
    def __init__(self, input_dim, hidden_dim, layer_dim, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, layer_dim, batch_first=True)
        self.drop = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim, 1)
    #    
    def forward(self, x):        
        out, _ = self.lstm(x)
        return self.fc(self.drop(out[:, -1, :])).squeeze(-1)
    
    
dl_model = LSTMModel(input_dim=len(lstm_features), hidden_dim=100, layer_dim=1)
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
    

# test_pred = (test_prob > 0.5).astype(int)
# xgb_pred = (dl_test['raw_prob'] > 0.5).astype(int)

# majority_class = int(round(dl_train["y"].mean()))
# majority_acc = accuracy_score(dl_test["y"], np.full_like(dl_test["y"], majority_class))


#==========================================================
# TO SQL DATABASE SECTION
#==========================================================

symbol_map_reverse = {0:'AAPL',1:'AMZN',2:'GOOGL',3:'MSFT',4:'NVDA'}


created_at = datetime.now(timezone.utc)

with engine.connect() as conn:
    print(conn.execute(text("SELECT sql FROM sqlite_master WHERE name = 'predictions'")).scalar())
    
typical_move = train_model["day_percentage_change"].abs().median() /100

def build_export(model_name, probs):
    preds = (probs >0.5).astype(int)
    price = dl_test['price']
    return pd.DataFrame({
        "ticker" : pd.Series(dl_test["syms"]).map(symbol_map_reverse).values,
        "prediction_date" : pd.to_datetime(dl_test["dates"]).strftime("%Y-%m-%d"),
        "predicted_close" : np.where(preds == 1, price * (1 + typical_move), price *(1 - typical_move)).round(2),
        "actual_close" : dl_test['next_close'].round(2),
        "confidence_score" : np.where(preds == 1, probs, 1 - probs).round(4),
        "direction" : np.where(preds == 1, "up", "down"),
        "prediction_type" : "next_day",
        "model_name" : model_name,
        "created_at" : created_at,
    })
    
export_df = pd.concat([
    build_export("xgboost", dl_test['raw_prob']),
    build_export("xgboost_lstm", test_prob),
], ignore_index=True)

export_df = export_df.sort_values(["prediction_date", "ticker", "model_name"]).reset_index(drop=True)

with engine.begin() as conn:
    
    conn.execute(
        text(
            "DELETE FROM predictions WHERE model_name IN ('xgboost', 'xgboost_lstm') "
            "AND prediction_date >= :start"
        ), {"start": export_df["prediction_date"].min()},
    )
    
    export_df.to_sql("predictions", conn, if_exists="append", index=False, chunksize=1000)


    
print(dfCloseFinal.groupby("symbol")["date"].agg(["min", "max", "count"]))

print(f"Wrote {len(export_df)} rows to the predictions table")