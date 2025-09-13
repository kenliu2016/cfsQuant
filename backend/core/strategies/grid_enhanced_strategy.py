"""Strategy: grid_enhanced_strategy
    Template strategy. Edit `run(df, params)` to implement.
"""
import pandas as pd
import numpy as np
import ta

DEFAULT_PARAMS = {
    "lookback": 120,              # (策略参数)动态边界回溯窗口
    "used_capital_ratio": 0.6,    # (策略参数)初始投入资金比例
    "trend_filter": True,         # (策略参数)是否启用趋势过滤
    "trend_window": 480,          # (策略参数)趋势过滤窗口
    "adx_threshold": 30,          # (策略参数)新增ADX阈值
    "stop_loss_range_multiplier": 0.6, # 【新增】(策略参数)网格下方止损范围乘数
}

def run(df: pd.DataFrame, params: dict):
    """
    动态网格策略核心逻辑
    :param df: 包含价格数据的DataFrame，必须有'open', 'high', 'low', 'close'列
    :param params: 策略参数
    :return: 包含'position'列的DataFrame
    """
    df = df.copy()
    
    # === 1. 计算中枢价格和网格边界 ===
    df['rolling_mean'] = df['close'].rolling(window=params['lookback']).mean()
    df['rolling_high'] = df['high'].rolling(window=params['lookback']).max()
    df['rolling_low'] = df['low'].rolling(window=params['lookback']).min()
    df['grid_range'] = (df['rolling_high'] - df['rolling_low']) / 2
    df['grid_upper'] = df['rolling_mean'] + df['grid_range']
    df['grid_lower'] = df['rolling_mean'] - df['grid_range']

    # === 2. 计算趋势和ADX ===
    df['trend_ma'] = df['close'].rolling(window=params['trend_window']).mean()
    df['trend_slope'] = df['trend_ma'].pct_change().rolling(window=5).mean()
    df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=params['trend_window'])

    # === 3. 计算目标网格位置 ===
    df['grid_pos'] = np.divide(
        df['close'] - df['grid_lower'], 
        df['grid_upper'] - df['grid_lower'], 
        out=np.full_like(df['close'], 0.5),
        where=(df['grid_upper'] - df['grid_lower']) != 0
    )
    df['grid_pos'] = np.clip(df['grid_pos'], 0, 1)

    # === 4. 仓位调整（考虑趋势过滤）===
    df['target_position'] = 1 - (df['grid_pos'] ** 2)

    if params.get('trend_filter', False):
        is_trending = df['adx'] > params['adx_threshold']
        up_trend_condition = (df['trend_slope'] > 0) & (df['close'] > df['rolling_mean']) & is_trending
        df.loc[up_trend_condition, 'target_position'] = np.clip(df['target_position'] - 0.5, 0, 1)
        down_trend_condition = (df['trend_slope'] < 0) & (df['close'] < df['rolling_mean']) & is_trending
        df.loc[down_trend_condition, 'target_position'] = np.clip(df['target_position'] - 0.5, 0, 1)

    # === 5. 【新增优化】整合策略层面的止损逻辑 ===
    # 当价格跌破下方网格一个指定倍数(stop_loss_range_multiplier)的grid_range幅度时，清仓止损
    stop_loss_multiplier = params.get('stop_loss_range_multiplier', 1.0)
    stop_loss_price = df['grid_lower'] - (df['grid_range'] * stop_loss_multiplier)
    stop_loss_condition = df['close'] < stop_loss_price
    
    # 在触发止损的K线上，将目标仓位强制设为0，这将覆盖上面所有的仓位计算结果
    df.loc[stop_loss_condition, 'target_position'] = 0
    
    # === 6. 应用最终的资金使用比例 ===
    used_capital_ratio = params.get("used_capital_ratio", 1.0)
    df['position'] = df['target_position'] * used_capital_ratio
    
    # 移除中间计算列，只保留回测引擎需要的列
    final_cols = ['open', 'high', 'low', 'close', 'volume', 'position']
    df = df[[col for col in final_cols if col in df.columns]]
    
    return df