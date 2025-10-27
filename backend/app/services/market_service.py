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
        
    def get_market_exchanges(self, active: bool = True, tenant_id: Optional[str] = None) -> pd.DataFrame:
        """
        获取所有可用的交易所列表
        
        Args:
            active: 是否只获取活跃的交易所
            tenant_id: 租户ID，为None时使用默认租户
            
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
            
    def get_market_codes(self, exchange: str = None, active: bool = True, tenant_id: Optional[str] = None) -> pd.DataFrame:
        """
        获取市场代码列表，可以按交易所过滤
        
        Args:
            exchange: 交易所代码，不提供则获取所有
            active: 是否只获取活跃的代码
            tenant_id: 租户ID，为None时使用默认租户
            
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


@cache_dataframe_result(expire_time=300)  # 5分钟缓存
def get_strong_weak_coins_enhanced() -> Dict[str, Any]:
    """
    获取增强版强势/弱势币种数据（包含24小时价格曲线）
    按照新逻辑计算：
    1. 24小时VMR = 24小时内总成交量 / 期初市值
    2. 24小时涨幅 = (当前收盘价 - 24小时前开盘价) / 24小时前开盘价
    3. VMR总分 = 15分钟VMR * 0.1 + 1小时VMR * 0.3 + 1天VMR * 0.6
    
    Returns:
        包含强势币种和弱势币种列表的字典
    """
    try:
        # 调试信息：函数开始执行
        logger.info("get_strong_weak_coins_enhanced函数开始执行")
        
        # 获取所有币种列表
        market_data_service = MarketDataService()
        symbols_df = market_data_service.get_market_codes()
        if symbols_df.empty:
            logger.info("symbols_df为空，直接返回空结果")
            return {"strong_coins": [], "weak_coins": []}
        
        symbols = symbols_df['symbol'].tolist()
        
        # 获取当前时间和24小时前的时间
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        # 将datetime对象转换为字符串格式
        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
        start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 简化查询逻辑，直接使用market_ohlcv_1h视图获取数据
        sql = """
        WITH latest_data AS (
            -- 获取每个币种的最新数据
            SELECT 
                symbol,
                close as current_close,
                market_cap as current_market_cap
            FROM (
                SELECT 
                    symbol, close, market_cap, bucket,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
                FROM market_ohlcv_1h
                WHERE symbol = ANY(:symbols)
            ) ranked
            WHERE rn = 1
        ),
        past_data AS (
            -- 获取每个币种24小时前的数据
            SELECT 
                symbol,
                open as past_open,
                market_cap as past_market_cap
            FROM (
                SELECT 
                    symbol, open, market_cap, bucket,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
                FROM market_ohlcv_1h
                WHERE symbol = ANY(:symbols)
                    AND bucket <= :start_time
            ) ranked
            WHERE rn = 1
        ),
        volume_data AS (
            -- 计算24小时内总成交量
            SELECT 
                symbol,
                SUM(quote_volume) as total_quote_volume
            FROM market_ohlcv_1h
            WHERE symbol = ANY(:symbols)
                AND bucket >= :start_time
                AND bucket <= :end_time
            GROUP BY symbol
        ),
        vmr_15m AS (
            -- 获取15分钟VMR值
            SELECT 
                symbol,
                vmr as vmr_15m
            FROM (
                SELECT 
                    symbol, vmr, bucket,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
                FROM market_ohlcv_15m
                WHERE symbol = ANY(:symbols2)
            ) ranked
            WHERE rn = 1
        ),
        vmr_1h AS (
            -- 获取1小时VMR值
            SELECT 
                symbol,
                vmr as vmr_1h
            FROM (
                SELECT 
                    symbol, vmr, bucket,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
                FROM market_ohlcv_1h
                WHERE symbol = ANY(:symbols3)
            ) ranked
            WHERE rn = 1
        ),
        vmr_1d AS (
            -- 获取1天VMR值
            SELECT 
                symbol,
                vmr as vmr_1d
            FROM (
                SELECT 
                    symbol, vmr, bucket,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
                FROM market_ohlcv_1d
                WHERE symbol = ANY(:symbols4)
            ) ranked
            WHERE rn = 1
        )
        SELECT 
            l.symbol,
            l.current_close,
            p.past_open,
            p.past_market_cap,
            v.total_quote_volume,
            -- 计算24小时涨幅：(当前收盘价 - 24小时前开盘价) / 24小时前开盘价
            CASE 
                WHEN p.past_open > 0 THEN ROUND(((l.current_close - p.past_open) / p.past_open), 4)
                ELSE 0.0
            END as gain_24h,
            -- 计算24小时VMR：24小时总成交量 / 期初市值
            CASE 
                WHEN p.past_market_cap > 0 THEN ROUND((v.total_quote_volume / p.past_market_cap), 4)
                ELSE 0.0
            END as vmr_24h,
            -- 计算VMR总分：15分钟VMR * 0.1 + 1小时VMR * 0.3 + 1天VMR * 0.6
            COALESCE(v15.vmr_15m, 0) * 0.1 + COALESCE(v1.vmr_1h, 0) * 0.3 + COALESCE(vd.vmr_1d, 0) * 0.6 as vmr_total
        FROM latest_data l
        LEFT JOIN past_data p ON l.symbol = p.symbol
        LEFT JOIN volume_data v ON l.symbol = v.symbol
        LEFT JOIN vmr_15m v15 ON l.symbol = v15.symbol
        LEFT JOIN vmr_1h v1 ON l.symbol = v1.symbol
        LEFT JOIN vmr_1d vd ON l.symbol = vd.symbol
        WHERE l.current_close IS NOT NULL 
            AND p.past_open IS NOT NULL
            AND v.total_quote_volume IS NOT NULL
        """
        
        # 调试信息：打印时间参数
        print(f"查询时间范围: {start_time_str} 到 {end_time_str}")
        print(f"查询币种数量: {len(symbols)}")
        if symbols:
            print(f"前5个币种: {symbols[:5]}")
        
        # 使用命名参数调用fetch_df
        df = fetch_df(sql, 
                     symbols=symbols, 
                     end_time=end_time_str,
                     start_time=start_time_str,
                     symbols2=symbols,
                     symbols3=symbols,
                     symbols4=symbols)
        
        # 调试信息：打印查询结果
        print(f"主查询返回数据行数: {len(df)}")
        if not df.empty:
            print(f"前5个币种数据: {df['symbol'].head().tolist()}")
        
        if df.empty:
            print("主查询返回空数据，直接返回空结果")
            return {"strong_coins": [], "weak_coins": []}
        
        # 获取前20个币种的24小时价格数据用于绘制曲线图
        top_symbols = df['symbol'].head(20).tolist()
        
        # 调试信息：打印top_symbols
        logger.info(f"top_symbols数量: {len(top_symbols)}")
        if top_symbols:
            logger.info(f"top_symbols前5个: {top_symbols[:5]}")
        
        # 如果top_symbols为空，直接返回空数据
        if not top_symbols:
            hourly_data = []
            logger.info("top_symbols为空，hourly_data设置为空列表")
        else:
            # 查询每个币种的24小时数据
            hourly_data = []
            for symbol in top_symbols:
                # 调试信息：开始查询币种的小时数据
                logger.info(f"开始查询币种 {symbol} 的小时数据")
                
                # 查询该币种最近24小时的数据
                sql_hourly = """
                SELECT 
                    close,
                    quote_volume,
                    bucket as timestamp
                FROM market_ohlcv_1h
                WHERE symbol = :symbol
                    AND bucket <= :end_time
                    AND bucket >= :start_time
                ORDER BY bucket ASC
                """
                
                df_hourly = fetch_df(sql_hourly, 
                    symbol=symbol,
                    end_time=end_time_str,
                    start_time=start_time_str
                )
                
                # 调试信息：打印查询结果
                logger.info(f"币种 {symbol} 查询到 {len(df_hourly)} 条小时数据")
                
                if not df_hourly.empty:
                    # 转换为列表格式，确保有24条数据
                    symbol_hourly_data = []
                    for _, row in df_hourly.iterrows():
                        symbol_hourly_data.append({
                            'close': float(row['close']) if row['close'] is not None else 0.0,
                            'quote_volume': float(row['quote_volume']) if row['quote_volume'] is not None else 0.0,
                            'timestamp': row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp'])
                        })
                    
                    # 如果数据不足24条，用最后一条数据填充
                    if len(symbol_hourly_data) < 24:
                        last_data = symbol_hourly_data[-1] if symbol_hourly_data else None
                        while len(symbol_hourly_data) < 24:
                            symbol_hourly_data.append(last_data)
                    
                    # 只取最近24条数据
                    symbol_hourly_data = symbol_hourly_data[-24:]
                    hourly_data.append(symbol_hourly_data)
                else:
                    # 如果没有数据，创建24条空数据
                    empty_data = []
                    for i in range(24):
                        empty_data.append({
                            'close': 0.0,
                            'quote_volume': 0.0,
                            'timestamp': (start_time + timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M:%S+00:00')
                        })
                    hourly_data.append(empty_data)
        
        # 处理计算结果
        coins_data = []
        
        # 创建symbol到hourly_data的映射
        symbol_to_hourly_data = {}
        for i, symbol in enumerate(top_symbols):
            if i < len(hourly_data):
                symbol_to_hourly_data[symbol] = hourly_data[i]
        
        # 调试信息：打印top_symbols和hourly_data的映射关系
        logger.info(f"top_symbols数量: {len(top_symbols)}")
        logger.info(f"hourly_data数量: {len(hourly_data)}")
        logger.info(f"symbol_to_hourly_data映射数量: {len(symbol_to_hourly_data)}")
        
        # 调试信息：检查df是否为空
        logger.info(f"df行数: {len(df)}")
        logger.info(f"df列名: {df.columns.tolist()}")
        
        for _, row in df.iterrows():
            symbol = row['symbol']
            gain_24h = float(row['gain_24h']) if row['gain_24h'] is not None else 0.0
            vmr_24h = float(row['vmr_24h']) if row['vmr_24h'] is not None else 0.0
            vmr_total = float(row['vmr_total']) if row['vmr_total'] is not None else 0.0
            
            # 获取该币种的24小时价格数据
            symbol_hourly_data = symbol_to_hourly_data.get(symbol, [])
            
            # 如果币种不在top_symbols中，查询该币种的小时数据
            if symbol not in symbol_to_hourly_data:
                # 调试信息：打印币种不在top_symbols中的情况
                logger.info(f"币种 {symbol} 不在top_symbols中，查询小时数据")
                
                # 查询该币种最近24小时的数据
                sql_hourly = """
                SELECT 
                    close,
                    quote_volume,
                    bucket as timestamp
                FROM market_ohlcv_1h
                WHERE symbol = :symbol
                    AND bucket <= :end_time
                    AND bucket >= :start_time
                ORDER BY bucket ASC
                """
                
                df_hourly = fetch_df(sql_hourly, 
                    symbol=symbol,
                    end_time=end_time_str,
                    start_time=start_time_str
                )
                
                # 调试信息：打印查询结果
                logger.info(f"币种 {symbol} 查询到 {len(df_hourly)} 条小时数据")
                
                if not df_hourly.empty:
                    # 转换为列表格式，确保有24条数据
                    symbol_hourly_data = []
                    for _, row in df_hourly.iterrows():
                        symbol_hourly_data.append({
                            'close': float(row['close']) if row['close'] is not None else 0.0,
                            'quote_volume': float(row['quote_volume']) if row['quote_volume'] is not None else 0.0,
                            'timestamp': row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp'])
                        })
                    
                    # 如果数据不足24条，用最后一条数据填充
                    if len(symbol_hourly_data) < 24:
                        last_data = symbol_hourly_data[-1] if symbol_hourly_data else None
                        while len(symbol_hourly_data) < 24:
                            symbol_hourly_data.append(last_data)
                    
                    # 只取最近24条数据
                    symbol_hourly_data = symbol_hourly_data[-24:]
                else:
                    # 如果没有数据，创建24条空数据
                    symbol_hourly_data = []
                    for i in range(24):
                        symbol_hourly_data.append({
                            'close': 0.0,
                            'quote_volume': 0.0,
                            'timestamp': (start_time + timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M:%S+00:00')
                        })
            
            coins_data.append({
                'symbol': symbol,
                'vmr': vmr_24h,  # 使用24小时VMR值
                'vmr_total': vmr_total,  # 使用VMR总分作为复合分数
                'gain_24h': gain_24h,
                'hourly_data': symbol_hourly_data
            })
        
        # 按24小时涨幅降序排序
        coins_sorted_by_gain = sorted(coins_data, key=lambda x: x['gain_24h'], reverse=True)
        
        # 调试信息：打印排序后的币种涨幅
        logger.info(f"排序后币种数量: {len(coins_sorted_by_gain)}")
        if coins_sorted_by_gain:
            logger.info(f"前5个强势币: {[coin['symbol'] for coin in coins_sorted_by_gain[:5]]}")
            logger.info(f"前5个强势币涨幅: {[coin['gain_24h'] for coin in coins_sorted_by_gain[:5]]}")
            logger.info(f"最后5个弱势币: {[coin['symbol'] for coin in coins_sorted_by_gain[-5:]]}")
            logger.info(f"最后5个弱势币涨幅: {[coin['gain_24h'] for coin in coins_sorted_by_gain[-5:]]}")
        
        # 前10为强势币，最后10为弱势币
        strong_coins = coins_sorted_by_gain[:10]
        weak_coins = coins_sorted_by_gain[-10:]  # 取最后10名作为弱势币
        
        # 调试信息：打印最终结果
        logger.info(f"强势币数量: {len(strong_coins)}")
        logger.info(f"弱势币数量: {len(weak_coins)}")
        
        return {
            "strong_coins": strong_coins,
            "weak_coins": weak_coins
        }
        
    except Exception as e:
        logger.error(f"获取增强版强势/弱势币种数据失败: {e}")
        return {"strong_coins": [], "weak_coins": []}


def _get_vmr_value(symbol: str, timeframe: str) -> float:
    """
    获取指定币种和时间框架的VMR值
    
    Args:
        symbol: 币种代码
        timeframe: 时间框架（15m, 1h, 1d）
        
    Returns:
        VMR值，如果获取失败返回0.0
    """
    try:
        # 根据时间框架确定对应的表名
        table_mapping = {
            '15m': 'market_ohlcv_15m',
            '1h': 'market_ohlcv_1h',
            '1d': 'market_ohlcv_1d'
        }
        
        table_name = table_mapping.get(timeframe)
        if not table_name:
            return 0.0
        
        # 查询最新的VMR值
        sql = f"""
        SELECT vmr 
        FROM {table_name} 
        WHERE symbol = :symbol 
        ORDER BY bucket DESC 
        LIMIT 1
        """
        
        df = fetch_df(sql, symbol=symbol)
        if not df.empty and 'vmr' in df.columns:
            return float(df.iloc[0]['vmr'])
        else:
            return 0.0
            
    except Exception as e:
        logger.error(f"获取{symbol}的{timeframe} VMR值失败: {e}")
        return 0.0


def _get_batch_vmr_values(self, symbols: List[str], timeframes: List[str]) -> Dict[str, float]:
    """
    批量获取多个币种在不同时间周期的VMR值
    
    Args:
        symbols: 币种代码列表
        timeframes: 时间周期列表
        
    Returns:
        包含各币种VMR值的字典
    """
    try:
        vmr_data = {}
        
        for timeframe in timeframes:
            # 根据时间周期确定时间范围
            if timeframe == '1h':
                hours = 1
            elif timeframe == '4h':
                hours = 4
            elif timeframe == '24h':
                hours = 24
            else:
                continue
                
            # 获取当前时间和指定小时前的时间
            from datetime import datetime, timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            # 将datetime对象转换为字符串格式
            end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
            start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # 批量查询所有币种的VMR数据，使用命名参数格式
            sql = """
            WITH latest_data AS (
                -- 获取每个币种的最新数据（当前时间）
                SELECT 
                    symbol, 
                    market_cap as current_market_cap
                FROM (
                    SELECT 
                        symbol, market_cap, bucket,
                        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
                    FROM market_ohlcv_1h
                    WHERE symbol = ANY(:symbols1) 
                        AND bucket <= :end_time1
                ) ranked
                WHERE rn = 1
            ),
            past_data AS (
                -- 获取每个币种指定小时前的数据
                SELECT 
                    symbol, 
                    market_cap as past_market_cap
                FROM (
                    SELECT 
                        symbol, market_cap, bucket,
                        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY ABS(EXTRACT(EPOCH FROM (bucket - :start_time1::timestamp))) ASC) as rn
                    FROM market_ohlcv_1h
                    WHERE symbol = ANY(:symbols2) 
                        AND bucket >= :start_time1::timestamp - INTERVAL '1 hour'
                        AND bucket <= :start_time1::timestamp + INTERVAL '1 hour'
                ) ranked
                WHERE rn = 1
            ),
            volume_data AS (
                -- 计算指定小时内总成交量
                SELECT 
                    symbol,
                    SUM(quote_volume) as total_quote_volume
                FROM market_ohlcv_1h
                WHERE symbol = ANY(:symbols3) 
                    AND bucket >= :start_time2::timestamp
                    AND bucket <= :end_time2::timestamp
                GROUP BY symbol
            )
            SELECT 
                l.symbol,
                p.past_market_cap,
                v.total_quote_volume,
                -- 计算VMR：指定小时内总成交量 / 期初市值
                CASE 
                    WHEN p.past_market_cap > 0 THEN ROUND((v.total_quote_volume / p.past_market_cap), 4)
                    ELSE 0.0
                END as vmr
            FROM latest_data l
            LEFT JOIN past_data p ON l.symbol = p.symbol
            LEFT JOIN volume_data v ON l.symbol = v.symbol
            WHERE p.past_market_cap IS NOT NULL 
                AND v.total_quote_volume IS NOT NULL
            """
            
            # 使用命名参数调用fetch_df
            df = fetch_df(sql, 
                         symbols1=symbols, 
                         end_time1=end_time_str,
                         symbols2=symbols,
                         start_time1=start_time_str,
                         start_time2=start_time_str,
                         end_time2=end_time_str,
                         symbols3=symbols)
            
            if not df.empty:
                for _, row in df.iterrows():
                    symbol = row['symbol']
                    vmr_value = float(row['vmr']) if row['vmr'] is not None else 0.0
                    vmr_data[f"{symbol}_{timeframe}"] = vmr_value
        
        return vmr_data
        
    except Exception as e:
        logger.error(f"批量获取VMR值失败: {e}")
        return {}





def _get_batch_24h_gains(symbols: List[str]) -> Dict[str, float]:
    """
    批量计算多个币种的24小时涨幅（优化性能）
    
    Args:
        symbols: 币种代码列表
        
    Returns:
        包含各币种24小时涨幅的字典
    """
    try:
        if not symbols:
            return {}
        
        # 获取所有币种列表
        market_service = MarketDataService()
        market_codes_df = market_service.get_market_codes()
        if market_codes_df.empty:
            return {"strong_coins": [], "weak_coins": []}
        symbols = market_codes_df['symbol'].tolist()
        
        # 获取当前时间和24小时前的时间
        from datetime import datetime, timedelta
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        # 将datetime对象转换为字符串格式
        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
        start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 批量查询所有币种的24小时数据，使用命名参数格式
        sql = """
        WITH latest_data AS (
            -- 获取每个币种的最新数据（当前时间）
            SELECT 
                symbol, 
                close as current_close,
                market_cap as current_market_cap,
                bucket as current_time
            FROM (
                SELECT 
                    symbol, close, market_cap, bucket,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
                FROM market_ohlcv_1h
                WHERE symbol = ANY(:symbols1) 
                    AND bucket <= :end_time1
            ) ranked
            WHERE rn = 1
        ),
        past_data AS (
            -- 获取每个币种24小时前的数据
            SELECT 
                symbol, 
                open as past_open,
                market_cap as past_market_cap,
                bucket as past_time
            FROM (
                SELECT 
                    symbol, open, market_cap, bucket,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY ABS(EXTRACT(EPOCH FROM (bucket - :start_time1::timestamp))) ASC) as rn
                FROM market_ohlcv_1h
                WHERE symbol = ANY(:symbols2) 
                    AND bucket >= :start_time1::timestamp - INTERVAL '1 hour'
                    AND bucket <= :start_time1::timestamp + INTERVAL '1 hour'
            ) ranked
            WHERE rn = 1
        ),
        volume_data AS (
            -- 计算24小时内总成交量
            SELECT 
                symbol,
                SUM(quote_volume) as total_quote_volume
            FROM market_ohlcv_1h
            WHERE symbol = ANY(:symbols3) 
                AND bucket >= :start_time2::timestamp
                AND bucket <= :end_time2::timestamp
            GROUP BY symbol
        ),
        hourly_data AS (
            -- 获取24小时内每个小时的数据用于绘制曲线图
            SELECT 
                symbol,
                bucket,
                close,
                quote_volume
            FROM market_ohlcv_1h
            WHERE symbol = ANY(:symbols4) 
                AND bucket >= :start_time3::timestamp
                AND bucket <= :end_time3::timestamp
            ORDER BY symbol, bucket
        )
        SELECT 
            l.symbol,
            l.current_close,
            l.current_market_cap,
            p.past_open,
            p.past_market_cap,
            v.total_quote_volume,
            -- 计算VMR：24小时内总成交量 / 期初市值
            CASE 
                WHEN p.past_market_cap > 0 THEN ROUND((v.total_quote_volume / p.past_market_cap), 4)
                ELSE 0.0
            END as vmr_24h,
            -- 计算涨幅：(当前收盘价 - 24小时前开盘价) / 24小时前开盘价
            CASE 
                WHEN p.past_open > 0 THEN ROUND(((l.current_close - p.past_open) / p.past_open), 4)
                ELSE 0.0
            END as gain_24h
        FROM latest_data l
        LEFT JOIN past_data p ON l.symbol = p.symbol
        LEFT JOIN volume_data v ON l.symbol = v.symbol
        WHERE l.current_close IS NOT NULL 
            AND p.past_open IS NOT NULL
            AND v.total_quote_volume IS NOT NULL
        """
        
        # 使用命名参数调用fetch_df
        df = fetch_df(sql, 
                     symbols1=symbols, 
                     end_time1=end_time_str,
                     symbols2=symbols,
                     start_time1=start_time_str,
                     symbols3=symbols,
                     start_time2=start_time_str,
                     end_time2=end_time_str,
                     symbols4=symbols,
                     start_time3=start_time_str,
                     end_time3=end_time_str)
        
        if df.empty:
            return {"strong_coins": [], "weak_coins": []}
        
        # 获取每个币种的24小时价格数据用于绘制曲线图
        hourly_sql = """
        SELECT 
            symbol,
            bucket,
            close,
            quote_volume
        FROM market_ohlcv_1h
        WHERE symbol = ANY(:symbols5) 
            AND bucket >= :start_time4::timestamp
            AND bucket <= :end_time4::timestamp
        ORDER BY symbol, bucket
        """
        
        hourly_df = fetch_df(hourly_sql, 
                           symbols5=symbols, 
                           start_time4=start_time_str, 
                           end_time4=end_time_str)
        hourly_data = {}
        if not hourly_df.empty:
            for symbol in symbols:
                symbol_data = hourly_df[hourly_df['symbol'] == symbol]
                hourly_data_list = []
                for _, row in symbol_data.iterrows():
                    hourly_data_list.append({
                        'close': float(row['close']) if row['close'] is not None else 0.0,
                        'quote_volume': float(row['quote_volume']) if row['quote_volume'] is not None else 0.0,
                        'timestamp': row['bucket'].isoformat() if hasattr(row['bucket'], 'isoformat') else str(row['bucket'])
                    })
                hourly_data[symbol] = hourly_data_list
        
        # 处理计算结果
        coins_data = []
        for _, row in df.iterrows():
            symbol = row['symbol']
            vmr_24h = float(row['vmr_24h']) if row['vmr_24h'] is not None else 0.0
            gain_24h = float(row['gain_24h']) if row['gain_24h'] is not None else 0.0
            
            # 获取该币种的24小时价格数据
            symbol_hourly_data = hourly_data.get(symbol, [])
            
            coins_data.append({
                'symbol': symbol,
                'vmr': vmr_24h,  # 使用24小时VMR作为总分数
                'gain_24h': gain_24h,
                'hourly_data': symbol_hourly_data
            })
        
        # 按24小时涨幅降序排序
        coins_sorted_by_gain = sorted(coins_data, key=lambda x: x['gain_24h'], reverse=True)
        
        # 前10为强势币，后10为弱势币
        strong_coins = coins_sorted_by_gain[:10]
        weak_coins = coins_sorted_by_gain[10:20]  # 取第11-20名作为弱势币
        
        return {
            "strong_coins": strong_coins,
            "weak_coins": weak_coins
        }
        
    except Exception as e:
        logger.error(f"获取增强版强势/弱势币种数据失败: {e}")
        return {"strong_coins": [], "weak_coins": []}
