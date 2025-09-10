"""
EMA Crossover Strategy
- position = 1 when ema_short > ema_long else 0
"""
import pandas as pd

DEFAULT_PARAMS = {"short":12, "long":26, "fee_rate":0.0005, "initial_capital":100000.0, "slippage":0.0}

def run(df: pd.DataFrame, params: dict):
    p = DEFAULT_PARAMS.copy(); p.update(params or {})
    short, long = int(p["short"]), int(p["long"])
    data = df.copy().sort_values("datetime").reset_index(drop=True)
    data["ema_s"] = data["close"].ewm(span=short, adjust=False).mean()
    data["ema_l"] = data["close"].ewm(span=long, adjust=False).mean()
    data["position"] = (data["ema_s"] > data["ema_l"]).astype(int)
    data["position"] = data["position"].shift(1).fillna(0).astype(int)
    return data
