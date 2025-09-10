"""
RSI Mean Reversion
- Buy when RSI below lower bound, Sell when RSI above upper bound
"""
import pandas as pd

DEFAULT_PARAMS = {"window":14, "upper":70, "lower":30, "fee_rate":0.0005, "initial_capital":1000000.0, "slippage":0.0}

def _rsi(series, window=14):
    delta = series.diff()
    up = delta.clip(lower=0).rolling(window).mean()
    down = -delta.clip(upper=0).rolling(window).mean()
    rs = up / (down.replace(0, 1e-9))
    return 100 - 100/(1+rs)

def run(df: pd.DataFrame, params: dict):
    p = DEFAULT_PARAMS.copy(); p.update(params or {})
    w = int(p["window"])
    data = df.copy().sort_values("datetime").reset_index(drop=True)
    data["rsi"] = _rsi(data["close"], w)
    data["signal"] = 0
    data.loc[data["rsi"] < p["lower"], "signal"] = 1
    data.loc[data["rsi"] > p["upper"], "signal"] = 0
    data["position"] = data["signal"].shift(1).fillna(0).astype(int)
    return data
