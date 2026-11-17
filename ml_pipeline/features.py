import pandas as pd

splits = [
    ('AAPL', '2020-08-31', 4),
    ('NVDA', '2021-07-20', 4),
    ('NVDA', '2024-06-10', 10),
    ('AMZN', '2022-06-06', 20),
    ('GOOGL', '2022-07-18', 20)
]

horizons = [2, 5, 50, 250]
future_predictions = []

for horizon in horizons:
    future_predictions += [f"Close_Ratio_{horizon}", f"Trend_{horizon}", f"Volatility_{horizon}"]
    
def build_features(dfCloseFinal):
    dfCloseFinal = dfCloseFinal.sort_values(["symbol", "date"]).reset_index(drop=True)
    
    #======================================================
    # CALCULATE THE TARGET - DAYS
    #======================================================
    
    dfCloseFinal['price_raw'] = dfCloseFinal['price']
    
    dfCloseFinal['split_factor'] = 1.0
    
    for symbol, split_date, ratio in splits:
        mask = (dfCloseFinal['symbol'] == symbol) & (dfCloseFinal['date'] < pd.Timestamp(split_date))
        dfCloseFinal.loc[mask, 'split_factor'] *= ratio
    
    dfCloseFinal['price'] = dfCloseFinal['price_raw'] / dfCloseFinal['split_factor']

    # calculate the difference of the current and previous row for each row in the symbol group
    dfCloseFinal['day_price_diff'] = dfCloseFinal.groupby('symbol')['price'].diff()


    # calculate the percentage of the current and previous row for each row in the symbol group
    dfCloseFinal['day_percentage_change'] = dfCloseFinal.groupby('symbol')['price'].pct_change() * 100
    
    dfCloseFinal['up_day'] = (dfCloseFinal['day_percentage_change'] > 0).astype(int)
    
    for horizon in horizons:
        rolling_avg = (dfCloseFinal.groupby('symbol')['price'].rolling(horizon).mean().reset_index(level=0, drop=True))
        
        dfCloseFinal[f"Close_Ratio_{horizon}"] = dfCloseFinal['price'] / rolling_avg
        
        dfCloseFinal[f"Trend_{horizon}"] = (dfCloseFinal.groupby('symbol')['up_day'].rolling(horizon).sum().reset_index(level=0, drop=True))
        
        dfCloseFinal[f"Volatility_{horizon}"] = (dfCloseFinal.groupby('symbol')['day_percentage_change'].rolling(horizon).std().reset_index(level=0, drop=True))
    
    return dfCloseFinal