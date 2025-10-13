"""Strategy: strategy_template
    模板策略：所有新策略都可以基于这个文件修改。
    策略参数：用于策略中控制逻辑运行,命名，取值，数量完全由用户自定义。
    引擎参数：用于调整策略的运行环境,不参与策略逻辑运算，用户只能微调取值范围。
"""

import pandas as pd
import numpy as np

# 策略参数（只包含逻辑相关）
DEFAULT_PARAMS = {
    "initial_capital": 1000000.0, # (引擎参数)初始资金
    "min_trade_amount": 100.0,    # (引擎参数)最小成交金额（货币单位）
    "min_trade_qty": 0.001,       # (引擎参数)最小成交数量（标的单位，0 表示不启用）
    "cooldown_bars": 2,           # (引擎参数)冷却周期（单位bar）
    "lot_size": 0.00001,          # (引擎参数)最小交易数量（如100股，或最小下单单位；0 表示不启用）
    "min_position_change": 0.02,  # (引擎参数)低于仓位变动门槛不出发交易（1%）
    "lookback": 20,               # (策略参数)回溯窗口
    "threshold": 0.01,            # (策略参数)触发阈值
    "trend_filter": False,        # (策略参数)是否启用趋势过滤
}

def run(df: pd.DataFrame, params: dict):
    """
    策略核心逻辑
    输入: 
        df - DataFrame，至少包含 [datetime, open, high, low, close, volume]
        params - dict，策略参数
    输出:
        DataFrame，至少包含 [datetime, close, position]
    """
    # 合并默认参数和外部参数
    p = DEFAULT_PARAMS.copy()
    p.update(params or {})

    # 拷贝并排序
    data = df.copy().sort_values("datetime").reset_index(drop=True)

    # === 示例逻辑：基于均线的简单仓位策略 ===
    data["ma"] = data["close"].rolling(p["lookback"], min_periods=1).mean()

    # 仓位规则：收盘价 > 均线则满仓，反之空仓
    data["position"] = np.where(data["close"] > data["ma"], 1.0, 0.0)

    # 趋势过滤（可选逻辑）
    if p["trend_filter"]:
        data["trend_dir"] = np.where(data["close"] > data["ma"], 1, -1)
        data["position"] = np.where(data["trend_dir"] < 0, 0.0, data["position"])

    # 返回必须字段
    return data[["datetime", "close", "position"]]