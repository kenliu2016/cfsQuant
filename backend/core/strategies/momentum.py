"""
Simple Momentum Strategy: buy if close > close.shift(n)
"""
import pandas as pd

DEFAULT_PARAMS = {"lookback":10, "fee_rate":0.0005, "initial_capital":100000.0, "slippage":0.0}

def run(df, params):
    p = DEFAULT_PARAMS.copy(); p.update(params or {})
    lb = int(p["lookback"])
    data = df.copy().sort_values("datetime").reset_index(drop=True)
    data["mom"] = data["close"] - data["close"].shift(lb)
    data["signal"] = (data["mom"] > 0).astype(int)
    data["position"] = data["signal"].shift(1).fillna(0).astype(int)
    return data
