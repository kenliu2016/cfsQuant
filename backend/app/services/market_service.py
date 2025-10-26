from common import LoggerFactory
from common.db import fetch_df
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Optional, Union, Dict, List, Tuple, Any
from functools import lru_cache
from .cache_service import (
    cache_dataframe_result, 
    DEFAULT_EXPIRE_TIME, 
    LONG_EXPIRE_TIME, 
    clear_market_data_cache
)
from ..main.tenant_context import get_current_tenant

# 使用LoggerFactory替换原有logger
logger = LoggerFactory.get_logger('market_service')

class DateTimeParser:
    """日期时间解析工具类"""
    
    @staticmethod
    @lru_cache(maxsize=128)
    def parse_datetime(dt_str: Union[str, datetime, int]) -> datetime:
        """解析各种格式的日期时间字符串，包括带毫秒和时区的ISO格式"""
        if isinstance(dt_str, datetime):
            return dt_str
        
        if isinstance(dt_str, (int, float)):
            try:
                return datetime.fromtimestamp(int(dt_str))
            except (ValueError, TypeError):
                return datetime.now()
        
        if not isinstance(dt_str, str):
            return datetime.now()
            
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%fZ",  # 支持带毫秒和时区的ISO格式
            "%Y-%m-%d"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
                
        # 尝试直接使用datetime.fromisoformat（Python 3.7+支持）
        try:
            # 处理带Z的情况
            if dt_str.endswith('Z'):
                dt_str = dt_str[:-1] + '+00:00'
            return datetime.fromisoformat(dt_str)
        except ValueError:
            pass
        
        return datetime.now()



class MarketDataService:
    """市场数据服务类"""
    
    def __init__(self):
        self.datetime_parser = DateTimeParser()
        self.logger = logger
    
    @staticmethod
    def _clamp(value: Union[int, float, None], min_value: float, max_value: float, default: float = 0.0) -> float:
        """将数值限制在指定范围内"""
        try:
            if value is None:
                return default
            return max(min_value, min(max_value, float(value)))
        except (TypeError, ValueError):
            return default
    
    def _format_datetime(self, value: Any) -> Optional[str]:
        """格式化日期时间为ISO字符串"""
        if value is None:
            return None
        try:
            if isinstance(value, pd.Timestamp):
                dt = value.to_pydatetime()
            else:
                dt = self.datetime_parser.parse_datetime(value)
            return dt.replace(microsecond=0).isoformat()
        except Exception:
            return None
        
    def get_market_exchanges(self, active: bool = True) -> pd.DataFrame:
        """
        获取所有可用的交易所列表
        
        Args:
            active: 是否只获取活跃的交易所
            
        Returns:
            交易所列表的DataFrame
        """
        try:
            sql = """
            SELECT DISTINCT exchange FROM market_codes
            WHERE 1=1
            """

            if active:
                sql += " AND active = TRUE"

            sql += " ORDER BY exchange"

            df = fetch_df(sql)
            self.logger.info(f"获取交易所列表成功，共{len(df)}条记录")
            return df
        except Exception as e:
            self.logger.error(f"获取交易所列表失败: {e}")
            return pd.DataFrame(columns=['exchange'])
            
    def get_market_codes(self, exchange: str = None, active: bool = True) -> pd.DataFrame:
        """
        获取市场代码列表，可以按交易所过滤
        
        Args:
            exchange: 交易所代码，不提供则获取所有
            active: 是否只获取活跃的代码
            
        Returns:
            市场代码列表的DataFrame，包含symbol, exchange, active等字段
        """
        try:
            sql = """
            SELECT symbol, exchange, active FROM market_codes
            WHERE 1=1
            """

            params = {}

            if exchange:
                sql += " AND exchange = :exchange"
                params['exchange'] = exchange
            
            if active:
                sql += " AND active = TRUE"
            
            sql += " ORDER BY symbol"
            
            df = fetch_df(sql, **params)
            self.logger.info(f"获取市场代码列表成功，共{len(df)}条记录")
            return df
        except Exception as e:
            self.logger.error(f"获取市场代码列表失败: {e}")
            return pd.DataFrame(columns=['symbol', 'exchange', 'active'])
    
    def get_market_base_score(self, exchange: Optional[str] = None, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        获取市场情绪相关指标（牛熊分数 + Fear & Greed）
        """
        bull_sql = """
            SELECT exchange, symbol, datetime, score, phase
            FROM indecator_bull_bear
            WHERE 1=1
        """
        params: Dict[str, Any] = {}
        if exchange:
            bull_sql += " AND exchange = :exchange"
            params["exchange"] = exchange
        if symbol:
            bull_sql += " AND symbol = :symbol"
            params["symbol"] = symbol
        bull_sql += " ORDER BY datetime DESC LIMIT 1"
        
        try:
            bull_df = fetch_df(bull_sql, **params) if params else fetch_df(bull_sql)
        except Exception as e:
            self.logger.error(f"查询牛熊指标失败: {e}")
            bull_df = pd.DataFrame()
        
        bull_data = {
            "score": 0.0,
            "phase": "Neutral",
            "updated_at": None
        }
        if not bull_df.empty:
            row = bull_df.iloc[0]
            bull_data["score"] = self._clamp(row.get("score"), -7, 7, 0.0)
            bull_data["phase"] = row.get("phase") or "Neutral"
            bull_data["updated_at"] = self._format_datetime(row.get("datetime"))
            bull_data["exchange"] = row.get("exchange")
            bull_data["symbol"] = row.get("symbol")
        
        fear_sql = """
            SELECT datetime, value, value_classification
            FROM indecator_fear_greed
            ORDER BY datetime DESC
            LIMIT 1
        """
        try:
            fear_df = fetch_df(fear_sql)
        except Exception as e:
            self.logger.error(f"查询恐惧贪婪指数失败: {e}")
            fear_df = pd.DataFrame()
        
        fear_data = {
            "value": 0.0,
            "classification": None,
            "updated_at": None
        }
        if not fear_df.empty:
            row = fear_df.iloc[0]
            fear_data["value"] = self._clamp(row.get("value"), 0, 100, 0.0)
            fear_data["classification"] = row.get("value_classification")
            fear_data["updated_at"] = self._format_datetime(row.get("datetime"))
        
        return {
            "bull_bear": bull_data,
            "fear_greed": fear_data
        }
        
        
    def _prepare_query_params(self, startTime: Union[str, datetime], 
                            endTime: Union[str, datetime]) -> Tuple[datetime, datetime]:
        """准备查询参数"""
        start_dt = self.datetime_parser.parse_datetime(startTime)
        end_dt = self.datetime_parser.parse_datetime(endTime)
        return start_dt, end_dt
    
    def get_candles(self, symbol: str, startTime: str, endTime: str, 
                    timeframe: str = "1m", page: Optional[int] = None, 
                    page_size: Optional[int] = None, exchange: str = "binance") -> Union[Tuple[pd.DataFrame, Dict], 
                                                            Tuple[pd.DataFrame, int, Dict]]:
        """
        重构的K线数据获取方法
        根据不同的timeframe直接从对应的表或视图获取数据，不需要代码层面的聚合
        支持的timeframe: 1m,3m,5m,15m,30m,1h,2h,4h,1d,2d,3d
        """
        try:
            # 参数验证和准备
            if not symbol or not startTime or not endTime:
                query_params = {"symbol": symbol, "startTime": startTime, "endTime": endTime, "timeframe": timeframe, "exchange": exchange}
                return (pd.DataFrame(), query_params) if page is None else (pd.DataFrame(), 0, query_params)
            
            start_dt, end_dt = self._prepare_query_params(startTime, endTime)
            
            # 根据timeframe确定对应的表或视图名
            timeframe_mapping = {
                "1m": "market_ohlcv_1m",
                "3m": "market_ohlcv_3m", 
                "5m": "market_ohlcv_5m",
                "15m": "market_ohlcv_15m",
                "30m": "market_ohlcv_30m",
                "1h": "market_ohlcv_1h",
                "2h": "market_ohlcv_2h",
                "4h": "market_ohlcv_4h",
                "1d": "market_ohlcv_1d",
                "2d": "market_ohlcv_2d",
                "3d": "market_ohlcv_3d"
            }
            
            # 获取对应的表或视图名，默认为1m
            table_name = timeframe_mapping.get(timeframe, "market_ohlcv_1m")
            
            # 确定时间字段：对于聚合视图使用bucket字段，对于原始表使用datetime字段
            time_field = "bucket" if timeframe != "1m" else "datetime"
            
            # 构建SQL查询
            sql = f"""
            SELECT {time_field} as datetime, symbol, open, high, low, close, volume
            FROM {table_name}
            WHERE symbol = :symbol AND exchange = :exchange AND {time_field} BETWEEN :startTime AND :endTime
            ORDER BY {time_field}
            """
            
            # 不使用分页时
            if page is None or page_size is None:
                try:
                    df = fetch_df(sql, symbol=symbol, exchange=exchange, startTime=start_dt, endTime=end_dt)
                    
                    # 不再需要代码层面的聚合，直接返回数据
                    # 创建查询参数dict
                    query_params = {"symbol": symbol, "startTime": startTime, "endTime": endTime, "timeframe": timeframe, "exchange": exchange}
                    return df, query_params
                except Exception as e:
                    # 其他异常处理
                    self.logger.error(f"获取K线数据失败: {str(e)}", exc_info=True)
                    # 创建查询参数dict
                    query_params = {"symbol": symbol, "startTime": startTime, "endTime": endTime, "timeframe": timeframe, "exchange": exchange}
                    return (pd.DataFrame(), query_params) if page is None else (pd.DataFrame(), 0, query_params)
            
            # 使用分页时
            offset = (page - 1) * page_size
            
            # 优化：限制最大页面大小，防止单次返回过多数据
            if page_size > 1000:
                page_size = 1000
            
            # 获取总条数的SQL
            count_sql = f"""
            SELECT COUNT(*) as count
            FROM {table_name}
            WHERE symbol = :symbol AND exchange = :exchange AND {time_field} BETWEEN :startTime AND :endTime
            """
            
            # 获取分页数据的SQL
            paginated_sql = sql + " LIMIT :limit OFFSET :offset"
            
            # 执行查询
            df = fetch_df(paginated_sql, symbol=symbol, exchange=exchange, startTime=start_dt, endTime=end_dt, limit=page_size, offset=offset)
            count_df = fetch_df(count_sql, symbol=symbol, exchange=exchange, startTime=start_dt, endTime=end_dt)
            total_count = int(count_df['count'].iloc[0]) if not count_df.empty else 0
            
            # 不再需要代码层面的聚合，直接返回数据
            # 创建查询参数dict
            query_params = {"symbol": symbol, "startTime": startTime, "endTime": endTime, "timeframe": timeframe, "exchange": exchange}
            print("使用分页查询参数:", query_params)

            return df, total_count, query_params
        except Exception as e:
            self.logger.error(f"获取分页K线数据失败: {str(e)}", exc_info=True)
            # 创建查询参数dict
            query_params = {"symbol": symbol, "startTime": startTime, "endTime": endTime, "timeframe": timeframe, "exchange": exchange}
            return pd.DataFrame(), 0, query_params


@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_latest_candles(symbol: str, timeframe: str = "1m", limit: int = 2, exchange: str = "binance") -> Tuple[pd.DataFrame, Dict]:
    """获取单个股票代码的最新K线数据"""
    # 验证参数
    if not symbol:
        query_params = {"symbol": symbol, "timeframe": timeframe, "limit": limit, "exchange": exchange}
        return pd.DataFrame(), query_params
    
    # 确保limit是有效的正整数
    limit = max(1, min(int(limit), 70000))  # 限制最大返回10000条记录
    
    # 根据timeframe选择对应的表名和时间字段
    timeframe_mapping = {
        '1m': ('market_ohlcv_1m', 'datetime'),
        '3m': ('market_ohlcv_3m', 'bucket'),
        '5m': ('market_ohlcv_5m', 'bucket'),
        '15m': ('market_ohlcv_15m', 'bucket'),
        '30m': ('market_ohlcv_30m', 'bucket'),
        '1h': ('market_ohlcv_1h', 'bucket'),
        '2h': ('market_ohlcv_2h', 'bucket'),
        '4h': ('market_ohlcv_4h', 'bucket'),
        '1d': ('market_ohlcv_1d', 'bucket'),
        '2d': ('market_ohlcv_2d', 'bucket'),
        '3d': ('market_ohlcv_3d', 'bucket')
    }
    
    table_name, time_field = timeframe_mapping.get(timeframe, ('market_ohlcv_1m', 'datetime'))
    
    # SQL查询，获取按时间倒序排列的最近N条记录
    sql = f"""
    SELECT {time_field} as datetime, symbol, open, high, low, close, volume
    FROM {table_name}
    WHERE symbol = :symbol AND exchange = :exchange
    ORDER BY {time_field} DESC
    LIMIT :limit
    """

    try:
        df = fetch_df(sql, symbol=symbol, exchange=exchange, limit=limit)
        
        # 检查数据是否为空
        if df.empty:
            query_params = {"symbol": symbol, "timeframe": timeframe, "limit": limit, "exchange": exchange}
            return pd.DataFrame(), query_params
        
        # 按时间升序排列，符合前端展示习惯
        if not df.empty:
            # 确保datetime列存在且不为NaN，然后再排序
            if 'datetime' in df.columns and not df['datetime'].isna().all():
                df = df.sort_values('datetime')
            # 检查symbol列是否存在，不存在则添加
            if 'symbol' not in df.columns:
                df['symbol'] = symbol
            _log_query_results(df)
        
        # 创建查询参数dict
        query_params = {"symbol": symbol, "timeframe": timeframe, "limit": limit, "exchange": exchange}
        
        # 修复datetime列的数据类型
        if not df.empty:
            # 确保datetime列是datetime64[ns]类型
            if 'datetime' in df.columns:
                # 尝试将datetime列转换为datetime64[ns]类型
                try:
                    # 如果是字符串类型，需要先转换
                    if pd.api.types.is_object_dtype(df['datetime']):
                        # 使用pd.to_datetime并设置errors='coerce'处理无效值
                        df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
                except Exception as e:
                    logger.error(f"转换datetime列失败: {e}")
            
            # 确保symbol列有正确的值
            if 'symbol' in df.columns:
                # 检查是否存在NaT或None值
                if df['symbol'].isna().any() or (df['symbol'].dtype == 'object' and all(pd.isna(x) or x == 'NaT' for x in df['symbol'])):
                    # 用传入的symbol值填充
                    df['symbol'] = symbol
            
            # 即使symbol列不存在，也添加它
            elif 'symbol' not in df.columns:
                df['symbol'] = symbol
        
        return df, query_params
    except Exception as e:
        logger.error(f"获取最新K线数据失败: {e}", exc_info=True)
        query_params = {"symbol": symbol, "timeframe": timeframe, "limit": limit, "exchange": exchange}
        return pd.DataFrame(), query_params



def _log_query_results(df: pd.DataFrame):
    """记录查询结果"""
    symbol_time_ranges = []
    for symbol, group in df.groupby('symbol'):
        min_time = group['datetime'].min()
        max_time = group['datetime'].max()
        symbol_time_ranges.append(f"{symbol}: [{min_time}, {max_time}]")
    
    logger.info(
        f"批量查询结果: total_rows={len(df)}, "
        f"total_columns={len(df.columns)}, "
        f"symbol_time_ranges={', '.join(symbol_time_ranges)}"
    )

# 提供清除特定代码缓存的函数，用于数据更新后刷新缓存
def refresh_market_data_cache(symbol: str = None):
    """
    刷新市场数据缓存
    如果提供了symbol，则只刷新该代码的缓存；否则刷新所有市场数据缓存
    """
    clear_market_data_cache(symbol)
    
# 添加批量数据更新后刷新缓存的函数
def update_market_data_and_refresh_cache(data, table_name, symbol=None):
    """
    更新市场数据并刷新相关缓存
    
    Args:
        data: 要更新的pandas DataFrame数据
        table_name: 数据库表名
        symbol: 可选，股票代码，如提供则只刷新该代码的缓存
    """
    from common.db import to_sql
    import sys
    import os
    
    # 添加项目根目录到Python路径，以便能够导入app模块
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    from common.logger import LoggerFactory
    
    # 使用项目统一的日志工具
    logger = LoggerFactory.get_logger("services.market")
    
    try:
        # 写入数据到数据库
        to_sql(data, table_name)
        # 成功更新市场数据到表 {table_name}的信息已省略，以减少日志输出
        
        # 刷新相关缓存
        refresh_market_data_cache(symbol)
        # 成功刷新市场数据缓存，代码: {symbol}的信息已省略，以减少日志输出
        
        return True
    except Exception as e:
        logger.error(f"更新市场数据失败: {e}")
        return False

# 创建MarketDataService实例
market_data_service = MarketDataService()

@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_candles(symbol: str, startTime: str, endTime: str, 
                timeframe: str = "1m", page: Optional[int] = None, 
                page_size: Optional[int] = None) -> Union[Tuple[pd.DataFrame, Dict], 
                                                        Tuple[pd.DataFrame, int, Dict]]:
    """
    模块级别的K线数据获取函数
    调用MarketDataService类的get_candles方法
    """
    return market_data_service.get_candles(symbol, startTime, endTime, timeframe, page, page_size)

# 添加模块级别的市场代码相关函数
@cache_dataframe_result(expire_time=LONG_EXPIRE_TIME)
def get_market_exchanges(active: bool = True, tenant_id: Optional[str] = None) -> pd.DataFrame:
    """
    模块级别的获取交易所列表函数
    """
    return market_data_service.get_market_exchanges(active, tenant_id)

@cache_dataframe_result(expire_time=LONG_EXPIRE_TIME)
def get_market_codes(exchange: str = None, active: bool = True, tenant_id: Optional[str] = None) -> pd.DataFrame:
    """
    模块级别的获取市场代码列表函数
    """
    return market_data_service.get_market_codes(exchange, active, tenant_id)

def get_market_base_score(exchange: Optional[str] = None, symbol: Optional[str] = None) -> Dict[str, Any]:
    """
    获取市场基准情绪指标
    """
    return market_data_service.get_market_base_score(exchange=exchange, symbol=symbol)
