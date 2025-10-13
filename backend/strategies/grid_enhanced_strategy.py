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
    "stop_loss_range_multiplier": 0.6, # (策略参数)网格下方止损范围乘数
}

def run(df: pd.DataFrame, params: dict):
    """
    动态网格策略核心逻辑
    :param df: 包含价格数据的DataFrame，必须有'open', 'high', 'low', 'close'列
    :param params: 策略参数
    :return: 字典，包含DataFrame和网格级别数据
    """
    try:
        df = df.copy()
        
        # 确保DataFrame不为空
        if df.empty:
            df['position'] = 0.0
            return {'data': df, 'grid_levels': []}
        
        # 确保必要的列存在
        required_columns = ['open', 'high', 'low', 'close']
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"缺少必要的列: {col}")
        
        # === 1. 计算中枢价格和网格边界 ===
        df['rolling_mean'] = df['close'].rolling(window=params['lookback']).mean()
        df['rolling_high'] = df['high'].rolling(window=params['lookback']).max()
        df['rolling_low'] = df['low'].rolling(window=params['lookback']).min()
        
        # 确保grid_range为非负数
        df['grid_range'] = (df['rolling_high'] - df['rolling_low']) / 2
        df['grid_range'] = df['grid_range'].clip(lower=0.0001)  # 防止为0
        
        df['grid_upper'] = df['rolling_mean'] + df['grid_range']
        df['grid_lower'] = df['rolling_mean'] - df['grid_range']
        
        # 确保grid_lower < grid_upper
        invalid_range = df['grid_lower'] >= df['grid_upper']
        if invalid_range.any():
            # 修复无效的范围
            mid_range = (df['grid_upper'] + df['grid_lower']) / 2
            df.loc[invalid_range, 'grid_lower'] = mid_range[invalid_range] - 0.001
            df.loc[invalid_range, 'grid_upper'] = mid_range[invalid_range] + 0.001

        # === 2. 计算趋势和ADX ===
        df['trend_ma'] = df['close'].rolling(window=params['trend_window']).mean()
        df['trend_slope'] = df['trend_ma'].pct_change(fill_method=None).rolling(window=5).mean()
        
        # 添加防御措施，避免ADX计算出错
        try:
            df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=params['trend_window'])
        except Exception as e:
            df['adx'] = 0.0

        # === 3. 计算目标网格位置 ===
        # 添加更严格的防御措施
        denominator = df['grid_upper'] - df['grid_lower']
        # 确保分母为正
        denominator = denominator.clip(lower=0.0001)
        
        df['grid_pos'] = (df['close'] - df['grid_lower']) / denominator
        df['grid_pos'] = np.clip(df['grid_pos'], 0, 1)
        # 处理NaN值
        df['grid_pos'] = df['grid_pos'].fillna(0.5)

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
        # 确保used_capital_ratio在0-1之间
        used_capital_ratio = max(0.0, min(1.0, used_capital_ratio))
        
        df['position'] = df['target_position'] * used_capital_ratio
        # 确保position在0-1之间
        df['position'] = df['position'].clip(0.0, 1.0)
        
        # 处理NaN值
        df['position'] = df['position'].fillna(0.0)
        
        # 移除中间计算列，只保留回测引擎需要的列
        final_cols = ['open', 'high', 'low', 'close', 'volume', 'position']
        df_result = df[[col for col in final_cols if col in df.columns]]
        
        # === 7. 计算网格级别数据 ===
        # 获取最近一次的网格参数
        last_idx = df.index[-1]
        current_lower = df.loc[last_idx, 'grid_lower']
        current_upper = df.loc[last_idx, 'grid_upper']
        current_range = current_upper - current_lower
        
        # 获取中枢价格
        current_mean = df.loc[last_idx, 'rolling_mean']
        
        # 生成网格级别并添加名称
        grid_levels = []
        
        # 添加中枢价格（价格中枢）
        grid_levels.append({
            'name': '价格中枢',
            'price': current_mean
        })
        
        # 生成中枢线以上的网格线（卖出线）
        sell_count = 2  # 卖出线数量
        for i in range(1, sell_count + 1):
            grid_price = current_mean + (current_range / 5) * i
            grid_levels.append({
                'name': f'卖出#{i}',
                'price': grid_price
            })
        
        # 生成中枢线以下的网格线（买入线）
        buy_count = 2  # 买入线数量
        for i in range(1, buy_count + 1):
            grid_price = current_mean - (current_range / 5) * i
            grid_levels.append({
                'name': f'买入#{i}',
                'price': grid_price
            })
        
        # 添加止损线（作为额外的买入线）
        stop_loss_multiplier = params.get('stop_loss_range_multiplier', 1.0)
        stop_loss_price = current_lower - (current_range * stop_loss_multiplier)
        grid_levels.append({
            'name': '止损线',
            'price': stop_loss_price
        })
        
        # 按价格排序
        grid_levels.sort(key=lambda x: x['price'])
        
        return {'data': df_result, 'grid_levels': grid_levels}
    except Exception as e:
        # 如果发生任何异常，仍然返回字典格式，确保包含grid_levels字段
        print(f"策略执行出错: {str(e)}")
        df_copy = df.copy()
        df_copy['position'] = 0.0
        # 确保只返回需要的列
        final_cols = ['open', 'high', 'low', 'close', 'volume', 'position']
        df_result = df_copy[[col for col in final_cols if col in df_copy.columns]]
        # 即使异常也返回空对象数组格式
        return {'data': df_result, 'grid_levels': []}