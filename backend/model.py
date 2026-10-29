import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import requests
import os
import torch
import torch.nn as nn

load_dotenv()

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
    
# Call to grab historical data from the past 10 years for top 5 companies
def fetchHistoricalData():
    print("Getting Historical Data")
    url = "https://data.alpaca.markets/v2/stocks/auctions?symbols=NVDA%2CMSFT%2CAMZN%2CGOOGL%2CAAPL&start=2016-10-20T00%3A00%3A00Z&end=2026-10-20T00%3A00%3A00Z&limit=10000&feed=sip"
    rows = []
    token = ""
    
    while True:
        if token != "":
            updatedUrl = f"{url}&page_token={token}"
        else:
            updatedUrl = url
        data = UniversalTry(updatedUrl).json()
        
        for symbol, days in data["auctions"].items():
            for day in days:
                for trade in day.get("o") or []:
                    rows.append({
                            "symbol":symbol,
                            "date":day["d"],
                            "auction":"open",
                            "condition": trade["c"],
                            "price": trade["p"],
                            "size": trade["s"],
                            "timestamp": trade["t"],
                            "exchange":trade["x"]
                            })
                for trade in day.get("c") or []:
                    rows.append({
                            "symbol":symbol,
                            "date":day["d"],
                            "auction":"close",
                            "condition": trade["c"],
                            "price": trade["p"],
                            "size": trade["s"],
                            "timestamp": trade["t"],
                            "exchange":trade["x"]
                        })
        token = data.get("next_page_token")
        if not token:
            break
    return pd.DataFrame(rows)

# Function to check if the CSV exists and to create a new one if not
def checkCSV():
    if not os.path.exists("HistoricalData.csv"):
        print("No file exists by this name, creating now")
        df = fetchHistoricalData()
        df.to_csv("HistoricalData.csv", index=False)

checkCSV()
df = pd.read_csv("HistoricalData.csv")


print(df.shape)

df.info()

print(df.isnull().sum())


df = pd.read_csv("HistoricalData.csv")


print(df.info())
print(df.describe())
print("Missing Values: ")
print(df.isnull().sum())
print("Duplicates: ")
print(df.index.duplicated().sum())


#======================================================
# PRE-PROCESSING
#======================================================

dfClose = df[df['auction'].str.contains('open') == False]
dfClose = dfClose[dfClose['condition'].str.contains("M") == False]
print(dfClose.duplicated(subset=["symbol", "date"]).sum())

dfCloseFinal = dfClose.sort_values(['symbol', 'date', 'size', 'timestamp'], ascending=True).drop_duplicates(['symbol', 'date'], keep="last")
dfCloseFinal.to_csv("HistoricalDataClose.csv", index=False)

# df = pd.read_csv("HistoricalDataClose.csv")
print(dfCloseFinal.info())
print(dfCloseFinal.shape)
print(dfCloseFinal.describe())
print("Missing Values: ")
print(dfCloseFinal.isnull().sum())
print("Duplicates: ")
print(dfCloseFinal.duplicated(subset=["symbol", "date"]).sum())


# convert date columnt to datetime type
dfCloseFinal['date'] = pd.to_datetime(dfCloseFinal["date"], format='%Y-%m-%d')

# sort the csv by symbols then by date
dfCloseFinal = dfCloseFinal.sort_values(['symbol', 'date'], ascending=True)

# reset the index for the dataframe
dfCloseFinal = dfCloseFinal.reset_index(drop=True)

dfCloseFinal.to_csv("HistoricalDataCloseFinal.csv", index=False)

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
# SET THE MODEL
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

# SET THE FEATURES / INPUTS FOR THE LSTM MODEL
lstm_features = future_predictions + ['xgb_prob']
sequence_len = 20

# FUNCTION TO SET THE X AND Y DATA FOR LSTM DL MODEL
def make_sequences(df, features, target, sequence_len):
    X = []
    y = []
    d = []
    for sym, g in df.groupby('symbol'):
        g = g.sort_values('date')
        f = g[features].values
        t = g[target].values
        dates = g['date'].values
        for i in range(sequence_len - 1, len(g)):
            X.append(f[i - sequence_len + 1 : i + 1])
            y.append(t[i])
            d.append(dates[i])
    return np.array(X), np.array(y)


# 
scaler = StandardScaler().fit(validate_model[lstm_features])
validate_model[lstm_features] = scaler.transform(validate_model[lstm_features])
test_model[lstm_features] = scaler.transform(test_model[lstm_features])

X_val_sequence, y_val_sequence = make_sequences(validate_model, lstm_features, 'target_day', sequence_len)
X_test_sequence, y_test_sequence = make_sequences(test_model, lstm_features, 'target_day', sequence_len)

# CONVERT THE DATA USING PYTORCH SO LSTM CAN USE SAID DATA
X_val_torch = torch.tensor(X_val_sequence, dtype=torch.float32)
y_val_torch = torch.tensor(y_val_sequence, dtype=torch.float32)
X_test_torch = torch.tensor(X_test_sequence, dtype=torch.float32)
y_test_torch = torch.tensor(y_test_sequence, dtype=torch.float32)

#======================================================
# SET THE DL MODEL - LSTM
#======================================================

# SET CLASS WITH OWN FUNCTIONS TO BE CALLED LATER
class LSTMModel(nn.Module):
    # SETS THE DIMENSIONS TO BE USED IN THE LSTM
    def __init__(self, input_dim, hidden_dim, layer_dim):
        super(LSTMModel, self).__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, layer_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, 1)
    #    
    def forward(self, x):        
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :]).squeeze(-1)
    
    
dl_model = LSTMModel(input_dim=len(lstm_features), hidden_dim=100, layer_dim=1)
criterion = nn.BCEWithLogitsLoss()
optimiser = torch.optim.Adam(dl_model.parameters(), lr=0.001)

num_epochs = 100

for epoch in range(num_epochs):
    dl_model.train()
    optimiser.zero_grad()
    
    loss = criterion(dl_model(X_val_torch), y_val_torch)
    loss.backward()
    optimiser.step()
    
    if (epoch + 1) % 10 == 0:
        print(f"Epoch [{epoch+1}/{num_epochs}], Loss: {loss.item():.4f}")
    
    
    
