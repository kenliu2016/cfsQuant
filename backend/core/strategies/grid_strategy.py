
"""Strategy: grid_strategy

    Template strategy. Edit `run(df, params)` to implement.
"""
import pandas as pd
import numpy as np

DEFAULT_PARAMS = {
    "grid_num": 10,
    "lookback": 30,             # 动态边界回溯天数
    "initial_capital": 1000000.0,
    "used_capital_ratio": 0.5,  # 初始投入资金比例，留一部分保证金
    "cooldown_bars": 2,               # 冷却周期（单位bar）
    "signal_threshold": 0.05,    # 仓位变化阈值，低于此不触发交易
    "stop_loss_pct": 0.1,        # 跌破下限百分比止损
    "take_profit_pct": 0.2,      # 超过收益百分比止盈
    "trend_window": 20,          # 趋势窗口
    "trend_filter": True         # 是否启用趋势过滤
}

def run(df: pd.DataFrame, params: dict):
    """
    全功能增强网格策略：
    - 动态边界 + 非线性仓位
    - 冷却时间限制
    - 仓位变化阈值过滤
    - 止损止盈
    - 资金动态分配
    - 趋势行情过滤
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
    last_signal_index = -p["cooldown_bars"]  # 用于冷却周期
    used_capital = p["initial_capital"] * p["used_capital_ratio"]
    entry_price = None
    signals = []

    positions = []
    buy_signal = []
    sell_signal = []

    for i in range(n):
        price = data.at[i, "close"]
        target_pos = data.at[i, "raw_position"]
        trend_dir = data.at[i, "trend_dir"]

        # 趋势过滤：只允许顺势开仓
        target_pos = target_pos if trend_dir > 0 else position

        # 仓位变化阈值
        if abs(target_pos - position) < p["signal_threshold"]:
            target_pos = position

        # 冷却判断
        if (i - last_signal_index) < p["cooldown_bars"]:
            target_pos = position

        signal = 0
        # 买卖信号判断
        if target_pos > position:
            signal = 1
            last_signal_index = i
            entry_price = price if entry_price is None else entry_price
        elif target_pos < position:
            signal = -1
            last_signal_index = i

        # 止损止盈
        if entry_price is not None:
            drawdown = (entry_price - price) / entry_price
            profit = (price - entry_price) / entry_price
            if drawdown >= p["stop_loss_pct"]:
                target_pos = 0.0
                signal = -1
            elif profit >= p["take_profit_pct"]:
                # 锁定部分利润
                target_pos = max(position * 0.5, target_pos)
                if target_pos < position:
                    signal = -1

        position = target_pos
        positions.append(position)
        signals.append(signal)
        buy_signal.append(1 if signal == 1 else 0)
        sell_signal.append(1 if signal == -1 else 0)

    data["position"] = positions
    data["signal"] = signals
    data["buy_signal"] = buy_signal
    data["sell_signal"] = sell_signal

    return data[["datetime", "close", "position", "signal", "buy_signal", "sell_signal"]]
