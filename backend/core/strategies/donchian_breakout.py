"""
Donchian Channel Breakout Strategy
- Long when price breaks above upper band; exit when breaks below lower band
"""
import pandas as pd

DEFAULT_PARAMS = {"window":20, "fee_rate":0.0005, "initial_capital":100000.0, "slippage":0.0}

def run(df, params):
    p = DEFAULT_PARAMS.copy(); p.update(params or {})
    w = int(p["window"])
    data = df.copy().sort_values("datetime").reset_index(drop=True)
    data["highest"] = data["high"].rolling(w).max()
    data["lowest"] = data["low"].rolling(w).min()
    data["signal"] = 0
    data.loc[data["close"] > data["highest"].shift(1), "signal"] = 1
    data.loc[data["close"] < data["lowest"].shift(1), "signal"] = 0
    data["position"] = data["signal"].shift(1).fillna(0).astype(int)
    return data
