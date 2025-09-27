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
            table_name = "day_realtime" if interval in ["1D", "1W", "1M"] else "minute_realtime"
            
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
def get_predictions(code: str, start: str, end: str, interval: str = None, page: int = None, page_size: int = None):
    """
    获取预测数据，使用缓存装饰器优化性能
    缓存过期时间：24小时（预测数据通常不会频繁变动）
    
    Args:
        code: 股票代码
        start: 开始时间
        end: 结束时间
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
        else:
            start_dt = start
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
        else:
            end_dt = end
    except ValueError:
        end_dt = datetime.now()
    
    sql = """
    SELECT datetime, code, open, high, low, close, volume
    FROM minute_prediction
    WHERE code = :code AND datetime BETWEEN :start AND :end
    ORDER BY datetime
    """
    
    # 不使用分页时
    if page is None or page_size is None:
        try:
            df = fetch_df(sql, code=code, start=start_dt, end=end_dt)
            
            # 直接使用原始interval参数调用聚合函数，interval映射逻辑已移至聚合函数内部
            if interval:
                df = aggregate_kline_data(df, interval)
            
            return df
        except Exception as e:
            # 其他异常处理
            logger.error(f"获取预测数据失败: {e}")
            return pd.DataFrame()
    
    # 使用分页时
    offset = (page - 1) * page_size
    
    # 获取总条数的SQL
    count_sql = """
    SELECT COUNT(*) as count
    FROM minute_prediction
    WHERE code = :code AND datetime BETWEEN :start AND :end
    """
    
    # 获取分页数据的SQL
    paginated_sql = sql + " LIMIT :limit OFFSET :offset"
    
    # 执行查询
    df = fetch_df(paginated_sql, code=code, start=start_dt, end=end_dt, limit=page_size, offset=offset)
    count_df = fetch_df(count_sql, code=code, start=start_dt, end=end_dt)
    total_count = int(count_df['count'].iloc[0]) if not count_df.empty else 0
    
    return df, total_count

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
    
    # 根据interval选择表名
    if interval in ["1D", "1W", "1M"]:
        table_name = "day_realtime"
    else:
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

def _handle_special_intervals(df: pd.DataFrame, interval: str, codes: list) -> pd.DataFrame:
    """处理周线和月线的特殊聚合"""
    if interval == "1W":
        return _handle_weekly_data(codes)
    elif interval == "1M":
        return _handle_monthly_data(codes)
    return df

def _handle_weekly_data(codes: list) -> pd.DataFrame:
    """处理周线数据"""
    all_weekly_data = []
    for code in codes:
        weekly_sql = """
        SELECT 
            MIN(datetime) as datetime,
            code,
            MIN(open) FILTER (WHERE datetime = (
                SELECT MIN(datetime) FROM day_realtime 
                WHERE code = :code AND TO_CHAR(datetime, 'IYYY-IW') = TO_CHAR(dr.datetime, 'IYYY-IW')
            )) as open,
            MAX(high) as high,
            MIN(low) as low,
            MAX(close) FILTER (WHERE datetime = (
                SELECT MAX(datetime) FROM day_realtime 
                WHERE code = :code AND TO_CHAR(datetime, 'IYYY-IW') = TO_CHAR(dr.datetime, 'IYYY-IW')
            )) as close,
            SUM(volume) as volume
        FROM day_realtime dr
        WHERE code = :code
        GROUP BY code, TO_CHAR(datetime, 'IYYY-IW')
        ORDER BY datetime DESC
        LIMIT 1
        """
        weekly_df = fetch_df(weekly_sql, code=code)
        if not weekly_df.empty:
            all_weekly_data.append(weekly_df)
    
    return pd.concat(all_weekly_data, ignore_index=True) if all_weekly_data else pd.DataFrame()

def _handle_monthly_data(codes: list) -> pd.DataFrame:
    """处理月线数据"""
    all_monthly_data = []
    for code in codes:
        monthly_sql = """
        SELECT 
            MIN(datetime) as datetime,
            code,
            MIN(open) FILTER (WHERE datetime = (
                SELECT MIN(datetime) FROM day_realtime 
                WHERE code = :code AND TO_CHAR(datetime, 'YYYY-MM') = TO_CHAR(dr.datetime, 'YYYY-MM')
            )) as open,
            MAX(high) as high,
            MIN(low) as low,
            MAX(close) FILTER (WHERE datetime = (
                SELECT MAX(datetime) FROM day_realtime 
                WHERE code = :code AND TO_CHAR(datetime, 'YYYY-MM') = TO_CHAR(dr.datetime, 'YYYY-MM')
            )) as close,
            SUM(volume) as volume
        FROM day_realtime dr
        WHERE code = :code
        GROUP BY code, TO_CHAR(datetime, 'YYYY-MM')
        ORDER BY datetime DESC
        LIMIT 1
        """
        monthly_df = fetch_df(monthly_sql, code=code)
        if not monthly_df.empty:
            all_monthly_data.append(monthly_df)
    
    return pd.concat(all_monthly_data, ignore_index=True) if all_monthly_data else pd.DataFrame()

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
