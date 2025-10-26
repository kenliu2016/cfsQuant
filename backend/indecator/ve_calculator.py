"""
VE（波动率效率）指标计算模块

该模块实现VE（Volatility Efficiency）指标的计算逻辑，用于衡量单位波动率产生的交易效率。

VE指标计算公式：
VE = 成交量效率 × 波动率效率
其中：
- 成交量效率 = 实际成交量 / 预期成交量
- 波动率效率 = 实际波动率 / 预期波动率

创建时间: 2025-01-14
"""

import pandas as pd
import numpy as np
from sqlalchemy import text
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class VolatilityEfficiencyCalculator:
    """
    VE（波动率效率）指标计算器
    
    该类负责计算VE指标，包括实际波动率、预期波动率、成交量效率等核心指标。
    """
    
    def __init__(self, engine):
        """
        初始化VE指标计算器
        
        参数:
            engine: 数据库引擎对象
        """
        self.engine = engine
        
    def fetch_ohlcv_data(self, exchange: str, symbol: str, timeframe: str = '1h', 
                        lookback_days: int = 30) -> pd.DataFrame:
        """
        获取指定交易对的OHLCV数据
        
        参数:
            exchange: 交易所名称
            symbol: 交易对符号
            timeframe: 时间周期，如'1h', '4h', '1d'等
            lookback_days: 回溯天数
            
        返回:
            pd.DataFrame: 包含OHLCV数据的DataFrame
        """
        try:
            # 根据时间周期选择对应的数据表
            table_map = {
                '1m': 'market_ohlcv_1m',
                '3m': 'market_ohlcv_3m', 
                '5m': 'market_ohlcv_5m',
                '15m': 'market_ohlcv_15m',
                '30m': 'market_ohlcv_30m',
                '1h': 'market_ohlcv_1h',
                '2h': 'market_ohlcv_2h',
                '4h': 'market_ohlcv_4h',
                '1d': 'market_ohlcv_1d',
                '2d': 'market_ohlcv_2d',
                '3d': 'market_ohlcv_3d'
            }
            
            table_name = table_map.get(timeframe, 'market_ohlcv_1h')
            
            sql = text(f"""
                SELECT 
                    bucket as datetime,
                    open, high, low, close, volume, quote_volume,
                    taker_buy_volume, taker_buy_qv, number_of_trades,
                    market_cap, vmr
                FROM {table_name}
                WHERE exchange = :exchange AND symbol = :symbol
                    AND bucket >= NOW() - INTERVAL '{lookback_days} days'
                ORDER BY bucket ASC
            """)
            
            with self.engine.begin() as conn:
                df = pd.read_sql(sql, conn, params={'exchange': exchange, 'symbol': symbol})
                
            if df.empty:
                logger.warning(f"未找到{exchange}-{symbol}在{timeframe}周期的数据")
                return pd.DataFrame()
                
            # 确保datetime列为datetime类型
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"获取{exchange}-{symbol}的OHLCV数据失败: {e}")
            return pd.DataFrame()
    
    def calculate_actual_volatility(self, df: pd.DataFrame, window: int = 20) -> float:
        """
        计算实际波动率
        
        参数:
            df: 包含价格数据的DataFrame
            window: 计算窗口大小
            
        返回:
            float: 年化波动率
        """
        if len(df) < 2:
            return 0.0
            
        try:
            # 计算对数收益率
            returns = np.log(df['close'] / df['close'].shift(1))
            returns = returns.dropna()
            
            if len(returns) < window:
                window = len(returns)
                
            # 计算滚动标准差并取平均作为实际波动率
            rolling_std = returns.rolling(window=window).std()
            actual_volatility = rolling_std.mean() * np.sqrt(252)  # 年化波动率
            
            return float(actual_volatility) if not np.isnan(actual_volatility) else 0.0
            
        except Exception as e:
            logger.error(f"计算实际波动率失败: {e}")
            return 0.0
    
    def calculate_expected_volatility(self, df: pd.DataFrame, window: int = 20) -> float:
        """
        计算预期波动率（基于历史波动率）
        
        参数:
            df: 包含价格数据的DataFrame
            window: 计算窗口大小
            
        返回:
            float: 预期波动率
        """
        if len(df) < window:
            return 0.0
            
        try:
            # 使用历史波动率的移动平均作为预期波动率
            returns = df['close'].pct_change()
            returns = returns.dropna()
            
            if len(returns) < window:
                window = len(returns)
                
            # 计算历史波动率的移动平均
            historical_volatility = returns.rolling(window=window).std()
            expected_volatility = historical_volatility.mean() * np.sqrt(252)  # 年化
            
            return float(expected_volatility) if not np.isnan(expected_volatility) else 0.0
            
        except Exception as e:
            logger.error(f"计算预期波动率失败: {e}")
            return 0.0
    
    def calculate_volume_efficiency(self, df: pd.DataFrame, window: int = 20) -> float:
        """
        计算成交量效率
        
        参数:
            df: 包含成交量数据的DataFrame
            window: 计算窗口大小
            
        返回:
            float: 成交量效率
        """
        if len(df) < window:
            return 1.0  # 数据不足时返回中性值
            
        try:
            # 计算当前成交量相对于历史均值的效率
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].rolling(window=window).mean().iloc[-1]
            
            if avg_volume == 0:
                return 1.0
                
            volume_efficiency = current_volume / avg_volume
            
            # 对极端值进行平滑处理
            volume_efficiency = min(max(volume_efficiency, 0.1), 10.0)
            
            return float(volume_efficiency)
            
        except Exception as e:
            logger.error(f"计算成交量效率失败: {e}")
            return 1.0
    
    def calculate_ve_indicator(self, exchange: str, symbol: str, timeframe: str = '1h',
                             lookback_days: int = 30) -> Dict[str, float]:
        """
        计算VE（波动率效率）指标
        
        参数:
            exchange: 交易所名称
            symbol: 交易对符号
            timeframe: 时间周期
            lookback_days: 回溯天数
            
        返回:
            Dict: 包含VE指标各组成部分的字典
        """
        # 获取OHLCV数据
        df = self.fetch_ohlcv_data(exchange, symbol, timeframe, lookback_days)
        
        if df.empty:
            return {
                've': 0.0,
                'actual_volatility': 0.0,
                'expected_volatility': 0.0,
                'volume_efficiency': 1.0,
                'volatility_efficiency': 1.0,
                'data_points': 0
            }
        
        # 计算各组成部分
        actual_volatility = self.calculate_actual_volatility(df)
        expected_volatility = self.calculate_expected_volatility(df)
        volume_efficiency = self.calculate_volume_efficiency(df)
        
        # 计算波动率效率
        if expected_volatility > 0:
            volatility_efficiency = actual_volatility / expected_volatility
            # 对极端值进行平滑处理
            volatility_efficiency = min(max(volatility_efficiency, 0.1), 10.0)
        else:
            volatility_efficiency = 1.0
        
        # 计算最终的VE指标
        ve = volume_efficiency * volatility_efficiency
        
        # 对最终结果进行标准化处理
        ve = min(max(ve, 0.1), 10.0)
        
        return {
            've': float(ve),
            'actual_volatility': float(actual_volatility),
            'expected_volatility': float(expected_volatility),
            'volume_efficiency': float(volume_efficiency),
            'volatility_efficiency': float(volatility_efficiency),
            'data_points': len(df)
        }
    
    def calculate_ve_for_multiple_symbols(self, exchange: str, symbols: List[str], 
                                         timeframe: str = '1h') -> Dict[str, Dict]:
        """
        批量计算多个交易对的VE指标
        
        参数:
            exchange: 交易所名称
            symbols: 交易对符号列表
            timeframe: 时间周期
            
        返回:
            Dict: 各交易对的VE指标结果
        """
        results = {}
        
        for symbol in symbols:
            try:
                ve_data = self.calculate_ve_indicator(exchange, symbol, timeframe)
                results[symbol] = ve_data
                logger.info(f"计算{exchange}-{symbol}的VE指标完成: {ve_data['ve']:.4f}")
            except Exception as e:
                logger.error(f"计算{exchange}-{symbol}的VE指标失败: {e}")
                results[symbol] = {'ve': 0.0, 'error': str(e)}
        
        return results


def fetch_active_usdt_symbols(engine, exchange: str = 'binance') -> List[str]:
    """
    获取活跃的USDT交易对列表
    
    参数:
        engine: 数据库引擎
        exchange: 交易所名称
        
    返回:
        List[str]: 活跃的USDT交易对列表
    """
    try:
        sql = text("""
            SELECT DISTINCT symbol 
            FROM market_codes 
            WHERE exchange = :exchange 
                AND active = true
                AND quotecurrency = 'USDT'
            ORDER BY symbol
        """)
        
        with engine.begin() as conn:
            result = conn.execute(sql, {'exchange': exchange})
            symbols = [row[0] for row in result]
            
        return symbols
        
    except Exception as e:
        logger.error(f"获取活跃USDT交易对失败: {e}")
        return []


def main():
    """
    VE指标计算模块的主函数（测试用）
    """
    # 这里需要实际的数据库引擎，测试时请替换为您的引擎
    from common.db import get_engine
    
    engine = get_engine()
    calculator = VolatilityEfficiencyCalculator(engine)
    
    # 测试单个交易对
    result = calculator.calculate_ve_indicator('binance', 'BTCUSDT', '1h')
    print(f"BTCUSDT VE指标结果: {result}")
    
    # 测试批量计算
    symbols = ['ETHUSDT', 'BNBUSDT', 'ADAUSDT']
    results = calculator.calculate_ve_for_multiple_symbols('binance', symbols)
    print(f"批量VE指标结果: {results}")


if __name__ == "__main__":
    main()