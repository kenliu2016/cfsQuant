"""
VE（波动率效率）指标服务模块
提供VE指标的计算、查询和缓存功能
"""

from common import LoggerFactory
from common.db import fetch_df, execute
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Any, Tuple
from functools import lru_cache
from .cache_service import cache_dataframe_result, DEFAULT_EXPIRE_TIME, LONG_EXPIRE_TIME
from ..main.tenant_context import get_current_tenant

logger = LoggerFactory.get_logger('ve_indicator_service')


class VEIndicatorService:
    """VE指标服务类"""
    
    def __init__(self):
        self.logger = logger
    
    def get_ve_data(self, symbol: str, timeframe: str = "1h", 
                   limit: int = 100, 
                   start_time: Optional[str] = None,
                   end_time: Optional[str] = None) -> pd.DataFrame:
        """
        获取VE指标数据
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期，默认1h
            limit: 返回数据条数限制
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            VE指标数据的DataFrame
        """
        try:
            # 构建查询SQL
            sql = """
            SELECT 
                symbol,
                timeframe,
                datetime,
                ve,
                actual_volatility,
                expected_volatility,
                volume_efficiency,
                created_at
            FROM indecator_ve
            WHERE symbol = :symbol AND timeframe = :timeframe
            """
            
            params = {
                'symbol': symbol,
                'timeframe': timeframe
            }
            
            # 添加时间范围过滤
            if start_time and end_time:
                sql += " AND datetime BETWEEN :start_time AND :end_time"
                params['start_time'] = start_time
                params['end_time'] = end_time
            elif start_time:
                sql += " AND datetime >= :start_time"
                params['start_time'] = start_time
            elif end_time:
                sql += " AND datetime <= :end_time"
                params['end_time'] = end_time
            else:
                # 如果没有时间范围，按时间倒序获取最新数据
                sql += " ORDER BY datetime DESC LIMIT :limit"
                params['limit'] = limit
            
            # 执行查询
            df = fetch_df(sql, **params)
            
            if df.empty:
                self.logger.info(f"未找到VE指标数据: symbol={symbol}, timeframe={timeframe}")
                return pd.DataFrame()
            
            # 确保datetime列格式正确
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
            
            self.logger.info(f"成功获取VE指标数据: symbol={symbol}, timeframe={timeframe}, 数据量={len(df)}")
            return df
            
        except Exception as e:
            self.logger.error(f"获取VE指标数据失败: symbol={symbol}, timeframe={timeframe}, 错误: {str(e)}")
            return pd.DataFrame()
    
    def get_latest_ve(self, symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
        """
        获取最新的VE指标值
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            
        Returns:
            最新的VE指标数据字典
        """
        try:
            sql = """
            SELECT 
                symbol,
                timeframe,
                datetime,
                ve,
                actual_volatility,
                expected_volatility,
                volume_efficiency,
                created_at
            FROM indecator_ve
            WHERE symbol = :symbol AND timeframe = :timeframe
            ORDER BY datetime DESC
            LIMIT 1
            """
            
            df = fetch_df(sql, symbol=symbol, timeframe=timeframe)
            
            if df.empty:
                self.logger.info(f"未找到最新的VE指标数据: symbol={symbol}, timeframe={timeframe}")
                return {}
            
            # 转换为字典格式
            row = df.iloc[0]
            result = {
                'symbol': row['symbol'],
                'timeframe': row['timeframe'],
                'datetime': row['datetime'].isoformat() if hasattr(row['datetime'], 'isoformat') else str(row['datetime']),
                've': float(row['ve']) if pd.notna(row['ve']) else 0.0,
                'actual_volatility': float(row['actual_volatility']) if pd.notna(row['actual_volatility']) else 0.0,
                'expected_volatility': float(row['expected_volatility']) if pd.notna(row['expected_volatility']) else 0.0,
                'volume_efficiency': float(row['volume_efficiency']) if pd.notna(row['volume_efficiency']) else 0.0,
                'created_at': row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at'])
            }
            
            self.logger.info(f"成功获取最新VE指标: symbol={symbol}, ve={result['ve']}")
            return result
            
        except Exception as e:
            self.logger.error(f"获取最新VE指标失败: symbol={symbol}, timeframe={timeframe}, 错误: {str(e)}")
            return {}
    
    def get_ve_summary(self, timeframe: str = "1h", 
                      limit: int = 50,
                      exchange: Optional[str] = None) -> pd.DataFrame:
        """
        获取VE指标汇总数据（按交易对分组的最新VE值）
        
        Args:
            timeframe: 时间周期
            limit: 返回交易对数量限制
            exchange: 交易所过滤
            
        Returns:
            VE指标汇总数据的DataFrame
        """
        try:
            sql = """
            WITH latest_ve AS (
                SELECT 
                    symbol,
                    MAX(datetime) as latest_datetime
                FROM indecator_ve
                WHERE timeframe = :timeframe
                GROUP BY symbol
            )
            SELECT 
                v.symbol,
                v.timeframe,
                v.datetime,
                v.ve,
                v.actual_volatility,
                v.expected_volatility,
                v.volume_efficiency,
                v.created_at
            FROM indecator_ve v
            INNER JOIN latest_ve l ON v.symbol = l.symbol AND v.datetime = l.latest_datetime
            WHERE v.timeframe = :timeframe
            """
            
            params = {'timeframe': timeframe}
            
            # 添加交易所过滤
            if exchange:
                sql += " AND v.symbol LIKE :exchange_pattern"
                params['exchange_pattern'] = f"%{exchange}%"
            
            sql += " ORDER BY v.ve DESC LIMIT :limit"
            params['limit'] = limit
            
            df = fetch_df(sql, **params)
            
            if df.empty:
                self.logger.info(f"未找到VE指标汇总数据: timeframe={timeframe}")
                return pd.DataFrame()
            
            self.logger.info(f"成功获取VE指标汇总数据: timeframe={timeframe}, 交易对数量={len(df)}")
            return df
            
        except Exception as e:
            self.logger.error(f"获取VE指标汇总数据失败: timeframe={timeframe}, 错误: {str(e)}")
            return pd.DataFrame()
    
    def save_ve_data(self, ve_data: Dict[str, Any]) -> bool:
        """
        保存VE指标数据到数据库
        
        Args:
            ve_data: VE指标数据字典
            
        Returns:
            保存是否成功
        """
        try:
            sql = """
            INSERT INTO indecator_ve (
                symbol, timeframe, datetime, ve, 
                actual_volatility, expected_volatility, volume_efficiency, created_at
            ) VALUES (
                :symbol, :timeframe, :datetime, :ve,
                :actual_volatility, :expected_volatility, :volume_efficiency, NOW()
            )
            ON CONFLICT (symbol, timeframe, datetime) 
            DO UPDATE SET
                ve = EXCLUDED.ve,
                actual_volatility = EXCLUDED.actual_volatility,
                expected_volatility = EXCLUDED.expected_volatility,
                volume_efficiency = EXCLUDED.volume_efficiency,
                created_at = NOW()
            """
            
            result = execute(sql, **ve_data)
            
            self.logger.info(f"成功保存VE指标数据: symbol={ve_data.get('symbol')}, timeframe={ve_data.get('timeframe')}, ve={ve_data.get('ve')}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存VE指标数据失败: symbol={ve_data.get('symbol')}, 错误: {str(e)}")
            return False


# 创建VE指标服务实例
ve_indicator_service = VEIndicatorService()


@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_ve_data(symbol: str, timeframe: str = "1h", 
               limit: int = 100, 
               start_time: Optional[str] = None,
               end_time: Optional[str] = None) -> pd.DataFrame:
    """
    模块级别的VE指标数据获取函数
    """
    return ve_indicator_service.get_ve_data(symbol, timeframe, limit, start_time, end_time)


def get_latest_ve(symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
    """
    模块级别的获取最新VE指标函数
    """
    return ve_indicator_service.get_latest_ve(symbol, timeframe)


@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_ve_summary(timeframe: str = "1h", 
                  limit: int = 50,
                  exchange: Optional[str] = None) -> pd.DataFrame:
    """
    模块级别的VE指标汇总数据获取函数
    """
    return ve_indicator_service.get_ve_summary(timeframe, limit, exchange)


def save_ve_data(ve_data: Dict[str, Any]) -> bool:
    """
    模块级别的VE指标数据保存函数
    """
    return ve_indicator_service.save_ve_data(ve_data)