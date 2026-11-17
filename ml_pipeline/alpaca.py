from dotenv import load_dotenv
import os
import requests
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy import text
from .settings import engine


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
        
# Call to grab historical data from the past 10 years for top 5 companies
def fetchHistoricalData(start="2016-11-15T01%3A02%3A03.123456789Z"):
    print("Getting Historical Data")
    url = f"https://data.alpaca.markets/v2/stocks/bars?symbols=AAPL%2CAMZN%2CGOOGL%2CMSFT%2CNVDA&timeframe=1D&start={start}&limit=1000&adjustment=raw&feed=sip&sort=asc"
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

#======================================================
# SAVING TO SQL DB
#======================================================

# create sql columns and ready db to be saved to sql database
def build_daily(df):
    dfOut = df.rename(columns={"symbol": "ticker"}).copy()
    
    dfOut["created_at"] = datetime.now(timezone.utc)
    dfOut["date"] = pd.to_datetime(dfOut["date"]).dt.date.astype(str)
    return dfOut[["ticker", "date", "open", "high", "low", "close", "volume", "created_at"]]

def refreshData():
    with engine.begin() as conn:
        last = conn.execute(text("SELECT MAX(date) FROM stock_data")).scalar()
        
    start = (pd.to_datetime(last) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    new = fetchHistoricalData(start)
    
    if new.empty:
        print("No new data")
        return

    build_daily(new).to_sql("stock_data", engine, if_exists="append", index=False, chunksize=1000)

def loadHistoricalData():
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM stock_data")).scalar()
        
    if count == 0:
        print("stock_data is empty, downloading new set")
        daily = build_daily(fetchHistoricalData())
        daily.to_sql("stock_data", engine, if_exists="append", index=False, chunksize=1000)
    else:
        refreshData()
        
    return pd.read_sql(
        text("SELECT ticker AS symbol, date, close AS price "
             "FROM stock_data ORDER BY ticker, date"), engine, parse_dates=["date"]
    )

