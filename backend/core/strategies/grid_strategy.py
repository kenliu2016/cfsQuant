
"""Strategy: grid_strategy

    Template strategy. Edit `run(df, params)` to implement.
"""
import pandas as pd
import numpy as np

DEFAULT_PARAMS = {
    "initial_capital": 1000000.0, # (引擎参数)初始资金
    "min_trade_amount": 100.0,    # (引擎参数)最小成交金额（货币单位）
    "min_trade_qty": 0.001,       # (引擎参数)最小成交数量（标的单位，0 表示不启用）
    "cooldown_bars": 2,           # (引擎参数)冷却周期（单位bar）
    "lot_size": 0.00001,          # (引擎参数)最小交易数量（如100股，或最小下单单位；0 表示不启用）
    "min_position_change": 0.02,  # (引擎参数)低于仓位变动门槛不出发交易（1%）
    "grid_num": 10,               # (策略参数)网格数量
    "lookback": 30,               # (策略参数)动态边界回溯窗口
    "trend_window": 20,           # (策略参数)趋势窗口
    "used_capital_ratio": 0.5,    # (策略参数)初始投入资金比例，留一部分保证金
    "stop_loss_pct": 0.1,         # (策略参数)跌破下限百分比止损
    "take_profit_pct": 0.2,       # (策略参数)超过收益百分比止盈
    "trend_filter": True          # (策略参数)是否启用趋势过滤
}

def run(df: pd.DataFrame, params: dict):
    """
    网格策略（只输出目标仓位）：
    - 动态边界 + 非线性仓位
    - 趋势过滤
    - 止损止盈
    """
    p = DEFAULT_PARAMS.copy()
    p.update(params or {})

    data = df.copy().sort_values("datetime").reset_index(drop=True)
    n = len(data)

    # 计算动态边界
    data["rolling_low"] = data["close"].rolling(p["lookback"], min_periods=1).min()
    data["rolling_high"] = data["close"].rolling(p["lookback"], min_periods=1).max()
    eps = 1e-9
    data["grid_pos"] = (data["close"] - data["rolling_low"]) / (data["rolling_high"] - data["rolling_low"] + eps)
    data["grid_pos"] = data["grid_pos"].clip(0, 1)

    # 非线性仓位（低位重仓，高位轻仓）
    data["raw_position"] = 1 - (data["grid_pos"] ** 2)

    # 趋势过滤（如启用）
    if p["trend_filter"]:
        data["trend_ma"] = data["close"].rolling(p["trend_window"], min_periods=1).mean()
        data["trend_dir"] = np.where(data["close"] > data["trend_ma"], 1, -1)
    else:
        data["trend_dir"] = 1  # 不过滤

    position = 0.0
    entry_price = None
    positions = []

    for i in range(n):
        price = data.at[i, "close"]
        target_pos = data.at[i, "raw_position"]
        trend_dir = data.at[i, "trend_dir"]

        # 趋势过滤：只允许顺势开仓
        target_pos = target_pos if trend_dir > 0 else position

        # 止损止盈
        if entry_price is not None:
            drawdown = (entry_price - price) / entry_price
            profit = (price - entry_price) / entry_price
            if drawdown >= p["stop_loss_pct"]:
                target_pos = 0.0
            elif profit >= p["take_profit_pct"]:
                # 锁定部分利润
                target_pos = max(position * 0.5, target_pos)

        # 更新仓位
        if target_pos != position:
            if position == 0 and target_pos > 0:
                entry_price = price
        position = target_pos
        positions.append(position)

    data["position"] = positions

    return data[["datetime", "close", "position"]]
