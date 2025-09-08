from ..db import fetch_df
from datetime import datetime, timedelta
import pandas as pd
from ..db import fetch_df
from .cache_service import (
    cache_dataframe_result,
    DEFAULT_EXPIRE_TIME,
    LONG_EXPIRE_TIME,
    clear_market_data_cache
)

@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_candles(code: str, start: str, end: str, interval: str = "1m", page: int = None, page_size: int = None):
    """
    获取K线数据，使用缓存装饰器优化性能
    缓存过期时间：5分钟
    
    Args:
        code: 股票代码
        start: 开始时间
        end: 结束时间
        interval: 时间间隔，默认1分钟
        page: 页码，从1开始，不提供则返回全部数据
        page_size: 每页数据量，不提供则返回全部数据
    
    Returns:
        分页数据时返回元组 (数据, 总条数)，否则返回数据
    """
    sql = """
    SELECT datetime, code, open, high, low, close, volume
    FROM minute_realtime
    WHERE code = :code AND datetime BETWEEN :start AND :end
    ORDER BY datetime
    """
    
    # 不使用分页时
    if page is None or page_size is None:
        return fetch_df(sql, code=code, start=start, end=end)
    
    # 使用分页时
    offset = (page - 1) * page_size
    
    # 获取总条数的SQL
    count_sql = """
    SELECT COUNT(*) as count
    FROM minute_realtime
    WHERE code = :code AND datetime BETWEEN :start AND :end
    """
    
    # 获取分页数据的SQL
    paginated_sql = sql + " LIMIT :limit OFFSET :offset"
    
    # 执行查询
    df = fetch_df(paginated_sql, code=code, start=start, end=end, limit=page_size, offset=offset)
    count_df = fetch_df(count_sql, code=code, start=start, end=end)
    total_count = int(count_df['count'].iloc[0]) if not count_df.empty else 0
    
    return df, total_count

@cache_dataframe_result(expire_time=LONG_EXPIRE_TIME)
def get_predictions(code: str, start: str, end: str, page: int = None, page_size: int = None):
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
    sql = """
    SELECT datetime, code, open, high, low, close, volume
    FROM minute_prediction
    WHERE code = :code AND datetime BETWEEN :start AND :end
    ORDER BY datetime
    """
    
    # 不使用分页时
    if page is None or page_size is None:
        return fetch_df(sql, code=code, start=start, end=end)
    
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
    df = fetch_df(paginated_sql, code=code, start=start, end=end, limit=page_size, offset=offset)
    count_df = fetch_df(count_sql, code=code, start=start, end=end)
    total_count = int(count_df['count'].iloc[0]) if not count_df.empty else 0
    
    return df, total_count

@cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
def get_daily_candles(code: str, start: str, end: str, page: int = None, page_size: int = None):
    """
    获取日线数据，使用缓存装饰器优化性能
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
    # Directly fetch daily candles from day_realtime table
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
        return fetch_df(sql, code=code, start=start, end=end)
    
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
    df = fetch_df(paginated_sql, code=code, start=start, end=end, limit=page_size, offset=offset)
    count_df = fetch_df(count_sql, code=code, start=start, end=end)
    total_count = int(count_df['count'].iloc[0]) if not count_df.empty else 0
    
    return df, total_count

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
        logger.info(f"成功更新市场数据到表 {table_name}")
        
        # 刷新相关缓存
        refresh_market_data_cache(code)
        logger.info(f"成功刷新市场数据缓存，代码: {code}")
        
        return True
    except Exception as e:
        logger.error(f"更新市场数据失败: {e}")
        return False
