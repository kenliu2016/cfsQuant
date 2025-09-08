"""
Demo strategy: SMA crossover with fractional position sizing, max_position cap, and slippage.

- Returns 'position' as fraction between 0 and 1 representing target percent of portfolio invested.
- DEFAULT_PARAMS:
    short, long: windows
    fee_rate: per-trade proportional cost
    initial_capital: starting cash
    max_position: maximum fraction of capital invested (0-1)
    slippage: price slippage applied at fills (fraction, e.g. 0.001 = 0.1%)
"""
import pandas as pd
import numpy as np

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
    max_pos = float(p.get("max_position",1.0))
    slippage = float(p.get("slippage",0.0))

    data = df.copy().sort_values("datetime").reset_index(drop=True)
    close = data["close"]

    data["ma_s"] = close.rolling(short, min_periods=1).mean()
    data["ma_l"] = close.rolling(long, min_periods=1).mean()

    # raw signal 0/1
    data["signal"] = (data["ma_s"] > data["ma_l"]).astype(int)

    # convert to target position fraction (allow fractional allocations)
    # when signal==1 -> target = max_pos, else 0
    data["position"] = data["signal"] * max_pos

    # shift to simulate execution next bar
    data["position"] = data["position"].shift(1).fillna(0.0).astype(float)

    return data
