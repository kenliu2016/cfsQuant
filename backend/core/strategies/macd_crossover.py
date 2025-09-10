"""
MACD Crossover Strategy
- Use MACD line crossing signal line
"""
import pandas as pd

DEFAULT_PARAMS = {"fast":12, "slow":26, "signal":9, "fee_rate":0.0005, "initial_capital":100000.0, "slippage":0.0}

def run(df, params):
    p = DEFAULT_PARAMS.copy(); p.update(params or {})
    fast, slow, sig = int(p["fast"]), int(p["slow"]), int(p["signal"])
    data = df.copy().sort_values("datetime").reset_index(drop=True)
    ema_fast = data["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = data["close"].ewm(span=slow, adjust=False).mean()
    data["macd"] = ema_fast - ema_slow
    data["macd_signal"] = data["macd"].ewm(span=sig, adjust=False).mean()
    data["signal"] = (data["macd"] > data["macd_signal"]).astype(int)
    data["position"] = data["signal"].shift(1).fillna(0).astype(int)
    return data
