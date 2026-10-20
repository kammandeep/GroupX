import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
import xgboost as xgb
import requests
import os

load_dotenv()

keyID = os.getenv("APCA_API_KEY_ID")
secretKeyID = os.getenv("APCA_API_SECRET_KEY")

print(keyID is not None, secretKeyID is not None)

headers = {
            "accept": "application/json",
            "APCA-API-KEY-ID": keyID,
            "APCA-API-SECRET-KEY": secretKeyID,
        }

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
    

def fetchHistoricalData():
    print("Getting Historical Data")
    url = "https://data.alpaca.markets/v2/stocks/auctions?symbols=AAPL%2CTSLA&start=2024-01-03T01%3A02%3A03.123456789Z&end=2024-01-04T01%3A02%3A03.123456789Z&limit=10000&feed=sip&sort=asc"
    response = UniversalTry(url)
    auction = response.json()["auctions"]
    rows = []
    for symbol, days in auction.items():
        for day in days:
            for trade in day.get("o", []):
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
            for trade in day.get("c", []):
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
    return pd.DataFrame(rows)

def checkCSV():
    if not os.path.exists("HistoricalData.csv"):
        print("No file exists by this name, creating now")
        df = fetchHistoricalData()
        df.to_csv("HistoricalData.csv", index=False)

checkCSV()
df = pd.read_csv("HistoricalData.csv")

#======================================================
# CALCULATE THE TARGET - DAYS
#======================================================

# LATEST DAY COMPARE WHETHER CLOSING TRADE WAS UP OR DOWN WITH PREVIOUS DAY

# REPEAT FOR EACH DAY THROUGH THE DATASET

# CREATE A COLUMN OF 1 FOR UP AND 0 FOR DOWN

# COLUMN IS NOW TARGET FOR ML MODEL

#======================================================
# CALCULATE THE TARGET - WEEKS
#======================================================

# SEGMENT DATASET BY LATEST FULL MON - FRI
# COMPARE LATEST WEEK TO WEEK BEFORE

# REPEAT FOR EACH WEEK THROUGH THE DATASET 

# CREATE A COLUMN OF 1 FOR UP AND 0 FOR DOWN

# COLUMN IS NOW TARGET FOR ML MODEL

#======================================================
# CALCULATE THE TARGET - MONTHS
#======================================================

# SEGMENT DATASET BY MONTH (ENSURE THIS IS CORRECT 31 FOR OCT 28 FOR FEB ETC)
# COMPARE OVERALL UP / DOWN WITH LAST WEEK

# CREATE A COLUMN OF 1 FOR UP AND 0 FOR DOWN

# COLUMN IS NOW TARGET FOR ML MODEL

#======================================================
# CALCULATE THE TARGET - YEARS
#======================================================

# SEGMENT DATASET BY YEAR (365 / 364 DAYS)
# COMPARE UP / DOWN WITH LAST YEAR
# REPEAT WITH LAST YEAR AND THE YEAR BEFORE

# CREATE A COLUMN OF 1 FOR UP AND 0 FOR DOWN

# COLUMN IS NOW TARGET FOR ML MODEL

#======================================================
# SET THE INPUTS
#======================================================

input = [
    
]


X = df[input]
y = df[""]

#======================================================
# SET THE MODEL
#======================================================

model = xgb.XGBClassifier(booster="gbtree", n_estimators=10, max_depth=2, learning_rate=0.1)

# TEST / TRAIN / VALIDATE SPLIT 15 / 15 / 70 SPLIT
# FIRST ISOLATE THE TEST DATA
X_train_val, X_test, y_train_val, y_test = train_test_split(
    X, y, test_size=0.15, random_state=42
)

# NEXT SET ASIDE THE NEXT 15% ( 0.15 / 0.85 = 17.6%) FOR VALIDATION
X_train, X_val, y_train, y_val = train_test_split(
    X_train_val, y_train_val, test_size=0.176, random_state=42
)



