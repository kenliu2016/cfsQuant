
"""Strategy: grid_enhanced_strategy
    Template strategy. Edit `run(df, params)` to implement.
"""
import pandas as pd
import numpy as np
import ta

DEFAULT_PARAMS = {
    "lookback": 50,               # (策略参数)动态边界回溯窗口
    "used_capital_ratio": 0.5,    # (策略参数)初始投入资金比例，留一部分保证金
    "trend_filter": True,         # (策略参数)是否启用趋势过滤
    "trend_window": 240,          # (策略参数)趋势过滤窗口
    "adx_threshold": 25,          # (策略参数)新增ADX阈值
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
    # 使用历史均价作为中枢，以lookback窗口的均价计算
    df['rolling_mean'] = df['close'].rolling(window=params['lookback']).mean()
    
    # 动态网格上下边界
    # 使用历史最高/最低价的均值作为网格范围的参考
    df['rolling_high'] = df['high'].rolling(window=params['lookback']).max()
    df['rolling_low'] = df['low'].rolling(window=params['lookback']).min()
    df['grid_range'] = (df['rolling_high'] - df['rolling_low']) / 2
    
    df['grid_upper'] = df['rolling_mean'] + df['grid_range']
    df['grid_lower'] = df['rolling_mean'] - df['grid_range']

    # === 2. 计算趋势和ADX ===
    # 趋势方向：使用trend_window的均线斜率
    df['trend_ma'] = df['close'].rolling(window=params['trend_window']).mean()
    df['trend_slope'] = df['trend_ma'].pct_change().rolling(window=5).mean()
    
    # 计算ADX
    df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=params['trend_window'])

    # === 3. 计算目标网格位置 ===
    # 归一化当前价格在网格中的位置
    df['grid_pos'] = (df['close'] - df['grid_lower']) / (df['grid_upper'] - df['grid_lower'])
    df['grid_pos'] = np.clip(df['grid_pos'], 0, 1) # 限制在0-1之间

    # === 4. 仓位调整（考虑趋势过滤）===
    # 非线性仓位：低位重仓，高位轻仓
    df['target_position'] = 1 - (df['grid_pos'] ** 2)

    # 趋势过滤: 只有在趋势明显时才应用
    if params['trend_filter']:
        # 当ADX高于阈值时，执行趋势过滤
        is_trending = df['adx'] > params['adx_threshold']
        
        # 趋势向上且价格位于网格上半区，减少多头仓位
        up_trend_condition = (df['trend_slope'] > 0) & (df['close'] > df['rolling_mean']) & is_trending
        df.loc[up_trend_condition, 'target_position'] = np.clip(df['target_position'] - 0.5, 0, 1)

        # 趋势向下且价格位于网格下半区，减少空头仓位（即增加多头仓位）
        down_trend_condition = (df['trend_slope'] < 0) & (df['close'] < df['rolling_mean']) & is_trending
        df.loc[down_trend_condition, 'target_position'] = np.clip(df['target_position'] + 0.5, 0, 1)

    # 将目标仓位重命名为'position'，供回测引擎使用
    df['position'] = df['target_position']
    
    return df
