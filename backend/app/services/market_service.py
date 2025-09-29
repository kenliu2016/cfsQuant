from ..common import LoggerFactory
from ..db import fetch_df
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Optional, Union, Dict, List, Tuple
from functools import lru_cache
from .cache_service import (
    cache_dataframe_result, 
    DEFAULT_EXPIRE_TIME, 
    LONG_EXPIRE_TIME, 
    clear_market_data_cache
)

# 使用LoggerFactory替换原有logger
logger = LoggerFactory.get_logger('market_service')

class DateTimeParser:
    """日期时间解析工具类"""
    
    @staticmethod
    @lru_cache(maxsize=128)
    def parse_datetime(dt_str: Union[str, datetime, int]) -> datetime:
        """解析各种格式的日期时间字符串"""
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
            "%Y-%m-%d"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        
        return datetime.now()

class KlineAggregator:
    """K线数据聚合优化器"""
    
    @staticmethod
    def aggregate_kline_data(df: pd.DataFrame, interval: str) -> pd.DataFrame:
        """优化的K线数据聚合"""
        if df.empty:
            return df
            
        required_columns = ['datetime', 'code', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"DataFrame必须包含以下列: {required_columns}")
        
        # 确保datetime列是datetime类型
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        # 优化：使用numpy进行聚合计算
        def aggregate_group(group):
            # 添加空组检查，防止KeyError和IndexError
            if group.empty:
                return pd.Series({
                    'open': None,
                    'high': None,
                    'low': None,
                    'close': None,
                    'volume': 0
                })
            return pd.Series({
                'open': group['open'].iloc[0],
                'high': group['high'].max(),
                'low': group['low'].min(),
                'close': group['close'].iloc[-1],
                'volume': group['volume'].sum()
            })
        
        # 设置resample规则
        freq = interval.lower().replace('m', 'min').replace('M', 'ME')
        
        # 使用groupby和transform进行向量化操作
        result_dfs = []
        for code, group in df.groupby('code'):
            # 确保group不为空再进行操作
            if not group.empty:
                group = group.set_index('datetime')
                resampled = group.resample(freq).apply(aggregate_group).dropna()
                if not resampled.empty:
                    resampled['code'] = code
                    result_dfs.append(resampled.reset_index())
            
        return pd.concat(result_dfs, ignore_index=True) if result_dfs else pd.DataFrame(columns=required_columns)

# 替换原有的aggregate_kline_data函数
aggregate_kline_data = KlineAggregator.aggregate_kline_data

class MarketDataService:
    """市场数据服务类"""
    
    def __init__(self):
        self.datetime_parser = DateTimeParser()
        self.logger = logger
        
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
            市场代码列表的DataFrame，包含code, name, exchange, excode等字段
        """
        try:
            sql = """
            SELECT code, exchange, active, excode FROM market_codes
            WHERE 1=1
            """
            
            params = {}
            
            if exchange:
                sql += " AND exchange = :exchange"
                params['exchange'] = exchange
            
            if active:
                sql += " AND active = TRUE"
            
            sql += " ORDER BY excode"
            
            df = fetch_df(sql, **params)
            self.logger.info(f"获取市场代码列表成功，共{len(df)}条记录")
            return df
        except Exception as e:
            self.logger.error(f"获取市场代码列表失败: {e}")
            return pd.DataFrame(columns=['code', 'exchange', 'active', 'excode'])
        
        
    def _prepare_query_params(self, start: Union[str, datetime], 
                            end: Union[str, datetime]) -> Tuple[datetime, datetime]:
        """准备查询参数"""
        start_dt = self.datetime_parser.parse_datetime(start)
        end_dt = self.datetime_parser.parse_datetime(end)
        return start_dt, end_dt
    
    def get_candles(self, code: str, start: str, end: str, 
                    interval: str = "1m", page: Optional[int] = None, 
                    page_size: Optional[int] = None) -> Union[Tuple[pd.DataFrame, Dict], 
                                                            Tuple[pd.DataFrame, int, Dict]]:
        """优化的K线数据获取方法"""
        try:
            # 参数验证和准备
            if not code or not start or not end:
                query_params = {"code": code, "start": start, "end": end, "interval": interval}
                return (pd.DataFrame(), query_params) if page is None else (pd.DataFrame(), 0, query_params)
            
            start_dt, end_dt = self._prepare_query_params(start, end)
            # 根据interval后缀确定表名
            if interval.endswith('m'):
                table_name = "minute_realtime"
            elif interval.endswith('h'):
                table_name = "hour_realtime"
            elif interval.endswith(('D', 'W', 'M')):
                table_name = "day_realtime"
            else:
                # 默认使用分钟表
                table_name = "minute_realtime"
            
            # 构建SQL查询
            sql = """
            SELECT datetime, code, open, high, low, close, volume
            FROM """ + table_name + """
            WHERE code = :code AND datetime BETWEEN :start AND :end
            ORDER BY datetime
            """
            
            # 不使用分页时
            if page is None or page_size is None:
                try:
                    df = fetch_df(sql, code=code, start=start_dt, end=end_dt)
                    
                    # 直接使用原始interval参数调用聚合函数，interval映射逻辑已移至聚合函数内部
                    df = aggregate_kline_data(df, interval)
                    
                    # 创建查询参数dict
                    query_params = {"code": code, "start": start, "end": end, "interval": interval}
                    return df, query_params
                except Exception as e:
                    # 其他异常处理
                    self.logger.error(f"获取K线数据失败: {str(e)}", exc_info=True)
                    # 创建查询参数dict
                    query_params = {"code": code, "start": start, "end": end, "interval": interval}
                    return (pd.DataFrame(), query_params) if page is None else (pd.DataFrame(), 0, query_params)
            
            # 使用分页时
            offset = (page - 1) * page_size
            
            # 优化：限制最大页面大小，防止单次返回过多数据
            if page_size > 1000:
                page_size = 1000
            
            # 获取总条数的SQL
            count_sql = """
            SELECT COUNT(*) as count
            FROM """ + table_name + """
            WHERE code = :code AND datetime BETWEEN :start AND :end
            """
            
            # 获取分页数据的SQL
            paginated_sql = sql + " LIMIT :limit OFFSET :offset"
            
            # 执行查询
            df = fetch_df(paginated_sql, code=code, start=start_dt, end=end_dt, limit=page_size, offset=offset)
            count_df = fetch_df(count_sql, code=code, start=start_dt, end=end_dt)
            total_count = int(count_df['count'].iloc[0]) if not count_df.empty else 0
            
            # 直接使用原始interval参数调用聚合函数，interval映射逻辑已移至聚合函数内部
            df = aggregate_kline_data(df, interval)
            
            # 创建查询参数dict
            query_params = {"code": code, "start": start, "end": end, "interval": interval}
            print("使用分页查询参数:", query_params)

            return df, total_count, query_params
        except Exception as e:
            self.logger.error(f"获取分页K线数据失败: {str(e)}", exc_info=True)
            # 创建查询参数dict
            query_params = {"code": code, "start": start, "end": end, "interval": interval}
            return pd.DataFrame(), 0, query_params


@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_daily_candles(code: str, start: str, end: str, interval: str = "1D", page: int = None, page_size: int = None):
    """
    获取日线数据，支持不同周期聚合，使用缓存装饰器优化性能
    缓存过期时间：5分钟
    
    Args:
        code: 股票代码
        start: 开始时间
        end: 结束时间
        interval: 时间间隔，支持1D(日),1W(周),1M(月)
        page: 页码，从1开始，不提供则返回全部数据
        page_size: 每页数据量，不提供则返回全部数据
    
    Returns:
        分页数据时返回元组 (数据, 总条数)，否则返回数据
    """
    # 转换日期时间参数
    try:
        if isinstance(start, str):
            if ' ' in start:
                start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
            elif 'T' in start:
                start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S")
            else:
                start_dt = datetime.strptime(start, "%Y-%m-%d")
        elif isinstance(start, datetime):
            start_dt = start
        else:
            # 如果start不是字符串也不是datetime类型，尝试转换
            try:
                start_dt = datetime.fromtimestamp(int(start))
            except (ValueError, TypeError):
                start_dt = datetime.strptime("2020-01-01", "%Y-%m-%d")
    except ValueError:
        start_dt = datetime.strptime("2020-01-01", "%Y-%m-%d")
    
    try:
        if isinstance(end, str):
            if ' ' in end:
                end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
            elif 'T' in end:
                end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S")
            else:
                end_dt = datetime.strptime(end, "%Y-%m-%d")
        elif isinstance(end, datetime):
            end_dt = end
        else:
            # 如果end不是字符串也不是datetime类型，尝试转换
            try:
                end_dt = datetime.fromtimestamp(int(end))
            except (ValueError, TypeError):
                end_dt = datetime.now()
    except ValueError:
        end_dt = datetime.now()
    
    # 获取日线数据
    sql = """
    SELECT 
        datetime,
        code,
        open,
        high,
        low,
        close,
        volume
    FROM day_realtime
    WHERE code = :code AND datetime BETWEEN :start AND :end
    ORDER BY datetime
    """
    
    # 不使用分页时
    if page is None or page_size is None:
        try:
            df = fetch_df(sql, code=code, start=start_dt, end=end_dt)
            
            # 直接使用原始interval参数调用聚合函数，interval映射逻辑已移至聚合函数内部
            df = aggregate_kline_data(df, interval)
            
            return df
        except Exception as e:
            logger.error(f"获取日线数据失败: {e}")
            return pd.DataFrame()
    
    # 使用分页时
    offset = (page - 1) * page_size
    
    # 获取总条数的SQL
    count_sql = """
    SELECT COUNT(*) as count
    FROM day_realtime
    WHERE code = :code AND datetime BETWEEN :start AND :end
    """
    
    # 获取分页数据的SQL
    paginated_sql = sql + " LIMIT :limit OFFSET :offset"
    
    # 执行查询
    try:
        df = fetch_df(paginated_sql, code=code, start=start_dt, end=end_dt, limit=page_size, offset=offset)
        count_df = fetch_df(count_sql, code=code, start=start_dt, end=end_dt)
        total_count = int(count_df['count'].iloc[0]) if not count_df.empty else 0
        
        # 直接使用原始interval参数调用聚合函数，interval映射逻辑已移至聚合函数内部
        df = aggregate_kline_data(df, interval)
        
        return df, total_count
    except Exception as e:
        logger.error(f"获取分页日线数据失败: {e}")
        return pd.DataFrame(), 0

@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_intraday(code: str, start: str, end: str, page: int = None, page_size: int = None):
    """
    获取分时数据，使用缓存装饰器优化性能
    缓存过期时间：5分钟
    
    Args:
        code: 股票代码
        start: 开始时间
        end: 结束时间
        page: 页码，从1开始，不提供则返回全部数据
        page_size: 每页数据量，不提供则返回全部数据
    
    Returns:
        分页数据时返回元组 (数据, 总条数)，否则返回数据
    """
    # minute bars directly
    return get_candles(code, start, end, '1m', page, page_size)

@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_batch_candles(codes: list, interval: str = "1m", limit: int = 1, timestamp: str = None):
    """批量获取多个股票代码的最新K线数据"""
    # 验证参数
    if not codes or not isinstance(codes, list):
        return pd.DataFrame()
    
    # 确保limit是有效的正整数
    limit = max(1, int(limit))
    
    # 根据interval后缀确定表名
    if interval.endswith('m'):
        table_name = "minute_realtime"
    elif interval.endswith('h'):
        table_name = "hour_realtime"
    elif interval.endswith(('D', 'W', 'M')):
        table_name = "day_realtime"
    else:
        # 默认使用分钟表
        table_name = "minute_realtime"
    
    sql = """
    WITH ranked_data AS (
        SELECT 
            datetime, code, open, high, low, close, volume,
            ROW_NUMBER() OVER (PARTITION BY code ORDER BY datetime DESC) AS rank
        FROM """ + table_name + """
        WHERE code IN :codes
    )
    SELECT datetime, code, open, high, low, close, volume
    FROM ranked_data
    WHERE rank <= :limit
    ORDER BY code, datetime DESC
    """
    
    try:
        df = fetch_df(sql, codes=tuple(codes), limit=limit)
        
        if interval in ["1W", "1M"] and not df.empty:
            df = _handle_special_intervals(df, interval, codes)
        else:
            df = aggregate_kline_data(df, interval)
        
        if not df.empty:
            _log_query_results(df)
        
        return df
    except Exception as e:
        logger.error(f"批量获取K线数据失败: {e}")
        return pd.DataFrame()

@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_latest_candles(code: str, interval: str = "1m", limit: int = 2) -> Tuple[pd.DataFrame, Dict]:
    """获取单个股票代码的最新K线数据"""
    # 验证参数
    if not code:
        query_params = {"code": code, "interval": interval, "limit": limit}
        return pd.DataFrame(), query_params
    
    # 确保limit是有效的正整数
    limit = max(1, min(int(limit), 70000))  # 限制最大返回10000条记录
    
    # 根据interval后缀确定表名
    if interval.endswith('m'):
        table_name = "minute_realtime"
    elif interval.endswith('h'):
        table_name = "hour_realtime"
    elif interval.endswith(('D', 'W', 'M')):
        table_name = "day_realtime"
    else:
        # 默认使用分钟表
        table_name = "minute_realtime"
    
    # SQL查询，获取按时间倒序排列的最近N条记录
    sql = """
    SELECT datetime, code, open, high, low, close, volume
    FROM """ + table_name + """
    WHERE code = :code
    ORDER BY datetime DESC
    LIMIT :limit
    """

    try:
        df = fetch_df(sql, code=code, limit=limit)
        
        # 检查数据是否为空
        if df.empty:
            query_params = {"code": code, "interval": interval, "limit": limit}
            return pd.DataFrame(), query_params
        
        # 对数据进行聚合处理
        if interval in ["1W", "1M"]:
            # 特殊处理周线和月线，使用专用的处理函数
            df = _handle_special_intervals(df, interval, [code], limit)
            # 周/月线数据已经在处理函数中排序并限制了结果数量
            # 添加调试信息，检查_handle_special_intervals返回的数据类型
            logger.debug(f"_handle_special_intervals返回后的数据类型:\n{df.dtypes}")
            logger.debug(f"_handle_special_intervals返回后的数据样例:\n{df.head()}")
        else:
            # 其他时间间隔使用通用聚合函数
            df = aggregate_kline_data(df, interval)
        
        # 按时间升序排列，符合前端展示习惯
        if not df.empty:
            # 确保datetime列存在且不为NaN，然后再排序
            if 'datetime' in df.columns and not df['datetime'].isna().all():
                df = df.sort_values('datetime')
            # 检查code列是否存在，不存在则添加
            if 'code' not in df.columns:
                df['code'] = code
            _log_query_results(df)
        
        # 创建查询参数dict
        query_params = {"code": code, "interval": interval, "limit": limit}
        
        # 修复周/月线数据中datetime和code列的问题
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
            
            # 确保code列有正确的值
            if 'code' in df.columns:
                # 检查是否存在NaT或None值
                if df['code'].isna().any() or (df['code'].dtype == 'object' and all(pd.isna(x) or x == 'NaT' for x in df['code'])):
                    # 用传入的code值填充
                    df['code'] = code
            
            # 即使code列不存在，也添加它
            elif 'code' not in df.columns:
                df['code'] = code
        
        return df, query_params
    except Exception as e:
        logger.error(f"获取最新K线数据失败: {e}", exc_info=True)
        query_params = {"code": code, "interval": interval, "limit": limit}
        return pd.DataFrame(), query_params

def _handle_special_intervals(df: pd.DataFrame, interval: str, codes: list, limit: int = 1) -> pd.DataFrame:
    """处理周线和月线的特殊聚合"""
    if interval == "1W":
        result = _handle_weekly_data_with_df(df.copy(), limit)
        return result
    elif interval == "1M":
        result = _handle_monthly_data_with_df(df.copy(), limit)
        return result
    return df

def _handle_weekly_data_with_df(df: pd.DataFrame, limit: int) -> pd.DataFrame:
    """使用传入的日线数据处理周线聚合"""
    if df.empty:
        return pd.DataFrame()
    
    # 打印前几行数据进行调试
    logger.debug(f"周线聚合前数据样例:\n{df.head()}")
    logger.debug(f"周线聚合前数据类型:\n{df.dtypes}")
    
    # 确保datetime列是datetime类型
    if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
        try:
            # 先检查是否是字符串类型
            if pd.api.types.is_object_dtype(df['datetime']):
                # 尝试多种格式解析
                formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d']
                for fmt in formats:
                    try:
                        df['datetime'] = pd.to_datetime(df['datetime'], format=fmt, errors='coerce')
                        if not df['datetime'].isna().all():
                            logger.info(f"成功将datetime列转换为datetime类型，使用格式: {fmt}")
                            break
                    except:
                        continue
            else:
                # 如果不是字符串，尝试直接转换
                df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
                logger.info(f"成功将datetime列转换为datetime类型")
        except Exception as e:
            logger.error(f"转换datetime列失败: {e}")
    
    # 保存code值
    code_value = df['code'].iloc[0] if not df['code'].empty else None
    logger.debug(f"保存的code值: {code_value}")
    
    # 创建ISO周列
    try:
        df['iso_week'] = df['datetime'].dt.strftime('%G-%V')
        logger.debug(f"ISO周列创建成功")
    except Exception as e:
        logger.error(f"创建ISO周列失败: {e}")
        # 如果失败，使用一个默认值
        df['iso_week'] = '2025-01'
    
    # 按周分组并聚合
    try:
        weekly_df = df.groupby('iso_week').agg({
            'datetime': 'max',  # 使用每周最后一天作为周线的时间戳
            'open': 'first',    # 每周第一个开盘价
            'high': 'max',      # 每周最高价
            'low': 'min',       # 每周最低价
            'close': 'last',    # 每周最后收盘价
            'volume': 'sum'     # 每周总成交量
        }).reset_index()
        
        # 添加code列
        weekly_df['code'] = code_value
        
        # 按时间倒序排序并限制结果数量
        weekly_df = weekly_df.sort_values('datetime', ascending=False).head(limit)
        
        # 重置索引
        weekly_df = weekly_df.reset_index(drop=True)
        
        logger.info(f"周线聚合成功，结果行数: {len(weekly_df)}")
        logger.debug(f"周线聚合结果样例:\n{weekly_df.head()}")
    except Exception as e:
        logger.error(f"周线聚合失败: {e}")
        weekly_df = pd.DataFrame()
    
    # 记录查询结果
    if not weekly_df.empty:
        _log_query_results(weekly_df)
    
    return weekly_df

def _handle_monthly_data_with_df(df: pd.DataFrame, limit: int) -> pd.DataFrame:
    """使用传入的日线数据处理月线聚合"""
    if df.empty:
        logger.info("输入数据为空，返回空DataFrame")
        return pd.DataFrame()
    
    # 打印前几行数据进行调试
    logger.debug(f"月线聚合前数据样例:\n{df.head()}")
    logger.debug(f"月线聚合前数据类型:\n{df.dtypes}")
    
    # 确保datetime列是datetime类型
    if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
        try:
            # 先检查是否是字符串类型
            if pd.api.types.is_object_dtype(df['datetime']):
                # 尝试多种格式解析
                formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d']
                for fmt in formats:
                    try:
                        df['datetime'] = pd.to_datetime(df['datetime'], format=fmt, errors='coerce')
                        if not df['datetime'].isna().all():
                            logger.info(f"成功将datetime列转换为datetime类型，使用格式: {fmt}")
                            break
                    except:
                        continue
            else:
                # 如果不是字符串，尝试直接转换
                df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
                logger.info(f"成功将datetime列转换为datetime类型")
        except Exception as e:
            logger.error(f"转换datetime列失败: {e}")
    
    # 保存code值
    code_value = df['code'].iloc[0] if not df['code'].empty else None
    logger.debug(f"保存的code值: {code_value}")
    
    # 创建年月列
    try:
        df['year_month'] = df['datetime'].dt.strftime('%Y-%m')
        logger.debug(f"年月列创建成功")
    except Exception as e:
        logger.error(f"创建年月列失败: {e}")
        # 如果失败，使用一个默认值
        df['year_month'] = '2025-01'
    
    # 按月分组并聚合
    try:
        monthly_df = df.groupby('year_month').agg({
            'datetime': 'max',  # 使用每月最后一天作为月线的时间戳
            'open': 'first',    # 每月第一个开盘价
            'high': 'max',      # 每月最高价
            'low': 'min',       # 每月最低价
            'close': 'last',    # 每月最后收盘价
            'volume': 'sum'     # 每月总成交量
        }).reset_index()
        
        # 添加code列
        monthly_df['code'] = code_value
        
        # 按时间倒序排序并限制结果数量
        monthly_df = monthly_df.sort_values('datetime', ascending=False).head(limit)
        
        # 重置索引
        monthly_df = monthly_df.reset_index(drop=True)
        
        logger.info(f"月线聚合成功，结果行数: {len(monthly_df)}")
        logger.debug(f"月线聚合结果样例:\n{monthly_df.head()}")
    except Exception as e:
        logger.error(f"月线聚合失败: {e}")
        monthly_df = pd.DataFrame()
    
    # 记录查询结果
    if not monthly_df.empty:
        _log_query_results(monthly_df)
    
    return monthly_df

def _log_query_results(df: pd.DataFrame):
    """记录查询结果"""
    code_time_ranges = []
    for code, group in df.groupby('code'):
        min_time = group['datetime'].min()
        max_time = group['datetime'].max()
        code_time_ranges.append(f"{code}: [{min_time}, {max_time}]")
    
    logger.info(
        f"批量查询结果: total_rows={len(df)}, "
        f"total_columns={len(df.columns)}, "
        f"code_time_ranges={', '.join(code_time_ranges)}"
    )

# 提供清除特定代码缓存的函数，用于数据更新后刷新缓存
def refresh_market_data_cache(code: str = None):
    """
    刷新市场数据缓存
    如果提供了code，则只刷新该代码的缓存；否则刷新所有市场数据缓存
    """
    clear_market_data_cache(code)
    
# 添加批量数据更新后刷新缓存的函数
def update_market_data_and_refresh_cache(data, table_name, code=None):
    """
    更新市场数据并刷新相关缓存
    
    Args:
        data: 要更新的pandas DataFrame数据
        table_name: 数据库表名
        code: 可选，股票代码，如提供则只刷新该代码的缓存
    """
    from ..db import to_sql
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # 写入数据到数据库
        to_sql(data, table_name)
        # 成功更新市场数据到表 {table_name}的信息已省略，以减少日志输出
        
        # 刷新相关缓存
        refresh_market_data_cache(code)
        # 成功刷新市场数据缓存，代码: {code}的信息已省略，以减少日志输出
        
        return True
    except Exception as e:
        logger.error(f"更新市场数据失败: {e}")
        return False

# 创建MarketDataService实例
market_data_service = MarketDataService()

@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_candles(code: str, start: str, end: str, 
                interval: str = "1m", page: Optional[int] = None, 
                page_size: Optional[int] = None) -> Union[Tuple[pd.DataFrame, Dict], 
                                                        Tuple[pd.DataFrame, int, Dict]]:
    """
    模块级别的K线数据获取函数
    调用MarketDataService类的get_candles方法
    """
    return market_data_service.get_candles(code, start, end, interval, page, page_size)

# 添加模块级别的市场代码相关函数
@cache_dataframe_result(expire_time=LONG_EXPIRE_TIME)
def get_market_exchanges(active: bool = True) -> pd.DataFrame:
    """
    模块级别的获取交易所列表函数
    """
    return market_data_service.get_market_exchanges(active)

@cache_dataframe_result(expire_time=LONG_EXPIRE_TIME)
def get_market_codes(exchange: str = None, active: bool = True) -> pd.DataFrame:
    """
    模块级别的获取市场代码列表函数
    """
    return market_data_service.get_market_codes(exchange, active)
