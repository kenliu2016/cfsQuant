"""
Bollinger Bands Mean Reversion
- Buy when price below lower band; sell when above upper band
"""
import pandas as pd

DEFAULT_PARAMS = {"window":20, "num_std":2, "fee_rate":0.0005, "initial_capital":100000.0, "slippage":0.0}

def run(df, params):
    p = DEFAULT_PARAMS.copy(); p.update(params or {})
    w = int(p["window"]); n = float(p["num_std"])
    data = df.copy().sort_values("datetime").reset_index(drop=True)
    data["mid"] = data["close"].rolling(w).mean()
    data["std"] = data["close"].rolling(w).std().fillna(0)
    data["upper"] = data["mid"] + n * data["std"]
    data["lower"] = data["mid"] - n * data["std"]
    data["signal"] = 0
    data.loc[data["close"] < data["lower"], "signal"] = 1
    data.loc[data["close"] > data["upper"], "signal"] = 0
    data["position"] = data["signal"].shift(1).fillna(0).astype(int)
    return data
