from ..db import fetch_df
from datetime import datetime, timedelta
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def aggregate_kline_data(df, interval):
    """
    对K线数据按不同周期聚合
    
    Args:
        df: K线数据DataFrame，必须包含datetime, code, open, high, low, close, volume列
        interval: 聚合周期，支持5T,15T,30T,H,4H,D,W,M
    
    Returns:
        聚合后的K线数据DataFrame
    """
    # 处理空DataFrame情况
    if df.empty:
        return df
    
    # 验证输入DataFrame是否包含必要的列
    required_columns = ['datetime', 'code', 'open', 'high', 'low', 'close', 'volume']
    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"DataFrame必须包含以下列: {required_columns}")
    
    # 确保datetime列是datetime类型
    if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
        df['datetime'] = pd.to_datetime(df['datetime'])
    
    # 设置聚合规则
    agg_dict = {
        'open': 'first',  # 开盘价取第一个
        'high': 'max',    # 最高价取最大值
        'low': 'min',     # 最低价取最小值
        'close': 'last',  # 收盘价取最后一个
        'volume': 'sum'   # 成交量求和
    }
    
    # 按code分组
    grouped = df.groupby('code')
    # 创建结果DataFrame
    aggregated_dfs = []
    
    # 对每个code进行聚合
    for code, group in grouped:
        # 按interval重新采样
        try:
            # 设置datetime为索引
            group = group.set_index('datetime')
            
            # 转换弃用的时间频率格式
            # 'T'(分钟) -> 'min', 'H'(小时) -> 'h'
            if 'T' in interval:
                # 处理分钟频率，如5T -> 5min
                freq = interval.replace('T', 'min')
            elif 'H' in interval:
                # 处理小时频率，如H -> h, 4H -> 4h
                freq = interval.lower()
            else:
                # 其他频率保持不变 (D, W, M)
                freq = interval
            
            # 重新采样并聚合
            resampled = group.resample(freq).agg(agg_dict).dropna()
            
            # 保留code列
            resampled['code'] = code
            
            # 重置索引，保留datetime列
            resampled = resampled.reset_index()
            
            # 添加到结果列表中
            aggregated_dfs.append(resampled)
        except Exception as e:
            # 处理聚合过程中的错误
            raise ValueError(f"聚合代码{code}时出错: {str(e)}")
    
    # 合并所有结果
    if aggregated_dfs:
        aggregated_df = pd.concat(aggregated_dfs)
        # 按datetime排序
        aggregated_df = aggregated_df.sort_values(['code', 'datetime'])
        # 重置索引
        aggregated_df = aggregated_df.reset_index(drop=True)
    else:
        # 如果没有数据，返回空的DataFrame但保持正确的列结构
        aggregated_df = pd.DataFrame(columns=['datetime', 'code', 'open', 'high', 'low', 'close', 'volume'])
    
    return aggregated_df


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
    
    # 根据interval选择表名
    if interval == "1d":
        table_name = "day_realtime"
    else:
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
            
            # 根据interval参数调用聚合函数
            if interval == "5m":
                df = aggregate_kline_data(df, "5T")
            elif interval == "15m":
                df = aggregate_kline_data(df, "15T")
            elif interval == "30m":
                df = aggregate_kline_data(df, "30T")
            elif interval == "1h":
                df = aggregate_kline_data(df, "H")
            elif interval == "4h":
                df = aggregate_kline_data(df, "4H")
            elif interval == "1d":
                df = aggregate_kline_data(df, "D")
            elif interval == "1w":
                df = aggregate_kline_data(df, "W")
            elif interval == "1M":
                df = aggregate_kline_data(df, "M")
                
            return df
        except Exception as e:
            # 其他异常处理
            logger.error(f"获取K线数据失败: {e}")
            return pd.DataFrame()
    
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
    try:
        df = fetch_df(paginated_sql, code=code, start=start_dt, end=end_dt, limit=page_size, offset=offset)
        count_df = fetch_df(count_sql, code=code, start=start_dt, end=end_dt)
        total_count = int(count_df['count'].iloc[0]) if not count_df.empty else 0
        
        # 根据interval参数调用聚合函数
        if interval == "5m":
            df = aggregate_kline_data(df, "5T")
        elif interval == "15m":
            df = aggregate_kline_data(df, "15T")
        elif interval == "30m":
            df = aggregate_kline_data(df, "30T")
        elif interval == "1h":
            df = aggregate_kline_data(df, "H")
        elif interval == "4h":
            df = aggregate_kline_data(df, "4H")
        elif interval == "1d":
            df = aggregate_kline_data(df, "D")
        elif interval == "1w":
            df = aggregate_kline_data(df, "W")
        elif interval == "1M":
            df = aggregate_kline_data(df, "M")
        
        return df, total_count
    except Exception as e:
        logger.error(f"获取分页K线数据失败: {e}")
        return pd.DataFrame(), 0

@cache_dataframe_result(expire_time=LONG_EXPIRE_TIME)
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
            
            # 根据interval参数调用聚合函数
            if interval == "1D":
                df = aggregate_kline_data(df, "D")
            elif interval == "1W":
                df = aggregate_kline_data(df, "W")
            elif interval == "1M":
                df = aggregate_kline_data(df, "M")
            
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
        return fetch_df(sql, code=code, start=start_dt, end=end_dt)
    
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
        
        # 根据interval参数调用聚合函数
        if interval == "1D":
            df = aggregate_kline_data(df, "D")
        elif interval == "1W":
            df = aggregate_kline_data(df, "W")
        elif interval == "1M":
            df = aggregate_kline_data(df, "M")
        
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
