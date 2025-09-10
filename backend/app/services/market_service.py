from ..db import fetch_df
from datetime import datetime, timedelta
import pandas as pd
from ..db import fetch_df, fetch_df_async
from .cache_service import (
    cache_dataframe_result,
    async_cache_dataframe_result,
    DEFAULT_EXPIRE_TIME,
    LONG_EXPIRE_TIME,
    clear_market_data_cache,
    async_clear_market_data_cache
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

@async_cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
async def aget_candles(code: str, start: str, end: str, interval: str = "1m", page: int = None, page_size: int = None):
    """
    异步获取K线数据，使用异步缓存装饰器优化性能
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
    # 优化：预先验证参数，避免不必要的缓存查找和数据库查询
    if not code or not start or not end:
        return pd.DataFrame() if page is None else (pd.DataFrame(), 0)
    
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
    
    # 优化：添加时间范围限制，防止查询过大的数据量
    max_date_range = timedelta(days=30)
    if end_dt - start_dt > max_date_range:
        start_dt = end_dt - max_date_range
    
    # 优化：根据时间间隔选择合适的表
    table_name = "minute_realtime"
    if interval == "1d":
        table_name = "day_realtime"
    
    sql = f"""
    SELECT datetime, code, open, high, low, close, volume
    FROM {table_name}
    WHERE code = :code AND datetime BETWEEN :start AND :end
    ORDER BY datetime
    """
    
    # 不使用分页时
    if page is None or page_size is None:
        return await fetch_df_async(sql, code=code, start=start_dt, end=end_dt)
    
    # 使用分页时
    offset = (page - 1) * page_size
    
    # 优化：限制最大页面大小，防止单次返回过多数据
    if page_size > 1000:
        page_size = 1000
    
    # 获取总条数的SQL
    count_sql = f"""
    SELECT COUNT(*) as count
    FROM {table_name}
    WHERE code = :code AND datetime BETWEEN :start AND :end
    """
    
    # 获取分页数据的SQL
    paginated_sql = sql + " LIMIT :limit OFFSET :offset"
    
    # 优化：并行执行查询，提高性能
    import asyncio
    df_task = fetch_df_async(paginated_sql, code=code, start=start_dt, end=end_dt, limit=page_size, offset=offset)
    count_task = fetch_df_async(count_sql, code=code, start=start_dt, end=end_dt)
    
    # 添加超时处理，避免单个查询阻塞太久
    try:
        df, count_df = await asyncio.wait_for(asyncio.gather(df_task, count_task), timeout=5.0)
    except asyncio.TimeoutError:
        # 超时处理，返回空数据
        return pd.DataFrame(), 0
    
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

@async_cache_dataframe_result(expire_time=LONG_EXPIRE_TIME)
async def aget_predictions(code: str, start: str, end: str, page: int = None, page_size: int = None):
    """
    异步获取预测数据，使用异步缓存装饰器优化性能
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
        return await fetch_df_async(sql, code=code, start=start_dt, end=end_dt)
    
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
    df = await fetch_df_async(paginated_sql, code=code, start=start_dt, end=end_dt, limit=page_size, offset=offset)
    count_df = await fetch_df_async(count_sql, code=code, start=start_dt, end=end_dt)
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
        # 成功更新市场数据到表 {table_name}的信息已省略，以减少日志输出
        
        # 刷新相关缓存
        refresh_market_data_cache(code)
        # 成功刷新市场数据缓存，代码: {code}的信息已省略，以减少日志输出
        
        return True
    except Exception as e:
        logger.error(f"更新市场数据失败: {e}")
        return False

# 异步版本：获取日线数据
@async_cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
async def aget_daily_candles(code: str, start: str, end: str, page: int = None, page_size: int = None):
    """
    异步获取日线数据，使用异步缓存装饰器优化性能
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
        return await fetch_df_async(sql, code=code, start=start_dt, end=end_dt)
    
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
    df = await fetch_df_async(paginated_sql, code=code, start=start_dt, end=end_dt, limit=page_size, offset=offset)
    count_df = await fetch_df_async(count_sql, code=code, start=start_dt, end=end_dt)
    total_count = int(count_df['count'].iloc[0]) if not count_df.empty else 0
    
    return df, total_count

# 异步版本：获取分时数据
@async_cache_dataframe_result(expire_time=DEFAULT_EXPIRE_TIME)
async def aget_intraday(code: str, start: str, end: str, page: int = None, page_size: int = None):
    """
    异步获取分时数据，使用异步缓存装饰器优化性能
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
    # 优化：预先验证参数，避免不必要的缓存查找
    if not code or not start or not end:
        return pd.DataFrame() if page is None else (pd.DataFrame(), 0)
    
    # 优化：对于大数据量查询，使用直接调用aget_candles
    result = await aget_candles(code, start, end, '1m', page, page_size)
    
    return result

# 异步版本：刷新市场数据缓存
async def arefresh_market_data_cache(code: str = None):
    """
    异步刷新市场数据缓存
    如果提供了code，则只刷新该代码的缓存；否则刷新所有市场数据缓存
    """
    await async_clear_market_data_cache(code)
    
# 异步版本：更新市场数据并刷新相关缓存
async def aupdate_market_data_and_refresh_cache(data, table_name, code=None):
    """
    异步更新市场数据并刷新相关缓存
    
    Args:
        data: 要更新的pandas DataFrame数据
        table_name: 数据库表名
        code: 可选，股票代码，如提供则只刷新该代码的缓存
    """
    from ..db import to_sql_async
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # 异步写入数据到数据库
        await to_sql_async(data, table_name)
        # 成功更新市场数据到表 {table_name}的信息已省略，以减少日志输出
        
        # 异步刷新相关缓存
        await arefresh_market_data_cache(code)
        # 成功刷新市场数据缓存，代码: {code}的信息已省略，以减少日志输出
        
        return True
    except Exception as e:
        logger.error(f"更新市场数据失败: {e}")
        return False
