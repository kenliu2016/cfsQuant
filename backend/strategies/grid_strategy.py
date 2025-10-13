
"""Strategy: grid_strategy

    Template strategy. Edit `run(df, params)` to implement.
"""
import pandas as pd
import numpy as np

DEFAULT_PARAMS = {
    "lookback": 50,               # (策略参数)动态边界回溯窗口
    "used_capital_ratio": 0.5,    # (策略参数)初始投入资金比例，留一部分保证金
    "trend_filter": True,         # (策略参数)是否启用趋势过滤
    "trend_window_short": 5,      # (策略参数)短期趋势窗口
    "trend_window_long": 20,      # (策略参数)长期趋势窗口
    "grid_smooth_factor": 0.5,    # (策略参数)趋势状态下拉大格子权重
}

def run(df: pd.DataFrame, params: dict):
    """
    改进版网格策略（只输出目标仓位）：
    - 动态网格间距（震荡/趋势切换）
    - 改进趋势过滤器
    - 非线性仓位（低位重仓，高位轻仓）
    """
    p = DEFAULT_PARAMS.copy()
    p.update(params or {})

    data = df.copy().sort_values("datetime").reset_index(drop=True)
    n = len(data)

    # 动态网格计算：滚动高低 + 趋势调整
    data["rolling_low"] = data["close"].rolling(p["lookback"], min_periods=1).min()
    data["rolling_high"] = data["close"].rolling(p["lookback"], min_periods=1).max()
    eps = 1e-9
    data["grid_pos"] = (data["close"] - data["rolling_low"]) / (data["rolling_high"] - data["rolling_low"] + eps)
    data["grid_pos"] = data["grid_pos"].clip(0, 1)

    # 改进趋势过滤器
    if p["trend_filter"]:
        # 短期与长期均线
        ma_short = data["close"].rolling(p["trend_window_short"], min_periods=1).mean()
        ma_long = data["close"].rolling(p["trend_window_long"], min_periods=1).mean()

        # 均线斜率：短期上涨 > 长期上涨 => 上升趋势
        slope_short = ma_short.diff()
        slope_long = ma_long.diff()
        trend_signal = np.where((slope_short > 0) & (slope_long > 0), 1,
                                np.where((slope_short < 0) & (slope_long < 0), -1, 0))
        data["trend_dir"] = trend_signal
    else:
        data["trend_dir"] = 1  # 不过滤

    # 动态网格调整：趋势时拉大格子，震荡时细格子
    trend_strength = data["trend_dir"].abs()
    smooth_factor = p["grid_smooth_factor"]
    data["grid_pos_adj"] = data["grid_pos"] ** (1 - smooth_factor * trend_strength)

    # 非线性仓位（低位重仓，高位轻仓）
    data["raw_position"] = 1 - (data["grid_pos_adj"] ** 2)

    position = 0.0
    positions = []

    for i in range(n):
        target_pos = data.at[i, "raw_position"]
        trend_dir = data.at[i, "trend_dir"]

        # 顺势交易：下降趋势保持原仓位
        target_pos = target_pos if trend_dir >= 0 else position

        position = target_pos
        positions.append(position)

    data["position"] = positions

    return data[["datetime", "close", "position"]]
