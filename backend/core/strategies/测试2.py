
"""Strategy: 测试2

    Template strategy. Edit `run(df, params)` to implement.
"""
import pandas as pd

DEFAULT_PARAMS = {
        "short": 5,
        "long": 20,
        "fee_rate": 0.0005,
        "initial_capital": 100000.0,
        "max_position": 1.0,
        "slippage": 0.0
    }

def run(df: pd.DataFrame, params: dict):
        p = DEFAULT_PARAMS.copy()
        p.update(params or {})
        short = int(p.get("short",5))
        long = int(p.get("long",20))
        data = df.copy().sort_values("datetime").reset_index(drop=True)
        data["ma_s"] = data["close"].rolling(short, min_periods=1).mean()
        data["ma_l"] = data["close"].rolling(long, min_periods=1).mean()
        data["position"] = (data["ma_s"] > data["ma_l"]).astype(int)
        data["position"] = data["position"].shift(1).fillna(0).astype(int)
        return data
