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
        interval: 前端传入的原始时间间隔参数，如1m,5m,15m,30m,1h,4h,1D等
    
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
            
            # 创建前端传入interval到聚合函数所需interval的映射表
            interval_mapping = {
                "1m": "1T",  # 1分钟
                "5m": "5T",  # 5分钟
                "15m": "15T",  # 15分钟
                "30m": "30T",  # 30分钟
                "60m": "H",  # 60分钟
                "1h": "H",   # 1小时
                "4h": "4H",  # 4小时
                "1D": "D",   # 1天
                "1W": "W",   # 1周
                "1M": "M",   # 1月
                # 可以根据需要添加更多映射
            }
            
            # 检查传入的interval是否在映射表中
            if interval in interval_mapping:
                # 使用映射后的interval
                processed_interval = interval_mapping[interval]
            else:
                # 对于不在映射表中的interval，直接使用
                processed_interval = interval
            
            # 转换弃用的时间频率格式
            # 'T'(分钟) -> 'min', 'H'(小时) -> 'h'
            if 'T' in processed_interval:
                # 处理分钟频率，如5T -> 5min
                freq = processed_interval.replace('T', 'min')
            elif 'H' in processed_interval:
                # 处理小时频率，如H -> h, 4H -> 4h
                freq = processed_interval.lower()
            else:
                # 其他频率保持不变 (D, W, M)
                freq = processed_interval
            
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
            
            # 直接使用原始interval参数调用聚合函数，interval映射逻辑已移至聚合函数内部
            df = aggregate_kline_data(df, interval)
            
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
        
        # 直接使用原始interval参数调用聚合函数，interval映射逻辑已移至聚合函数内部
        df = aggregate_kline_data(df, interval)
        
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
    """
    批量获取多个股票代码的最新K线数据，使用缓存装饰器优化性能
    缓存过期时间：5分钟
    
    Args:
        codes: 股票代码列表
        interval: 时间间隔，默认1分钟
        limit: 返回的记录数量，默认1条，设置为2可以获取最近两个bar的数据
    
    Returns:
        包含多个股票代码最新数据的DataFrame
    """
    # 仅保留必要的错误日志记录
    import logging
    logger = logging.getLogger("market_service")
    
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
    
    # 构建SQL查询，使用IN子句查询多个代码的最新数据
    # 对于每个代码，获取最新的指定数量的记录
    sql = """
    WITH ranked_data AS (
        SELECT 
            datetime, 
            code, 
            open, 
            high, 
            low, 
            close, 
            volume,
            ROW_NUMBER() OVER (PARTITION BY code ORDER BY datetime DESC) AS rank
        FROM 
            """ + table_name + """
        WHERE 
            code IN :codes
    )
    SELECT 
        datetime, 
        code, 
        open, 
        high, 
        low, 
        close, 
        volume
    FROM 
        ranked_data
    WHERE 
        rank <= :limit
    ORDER BY 
        code, datetime DESC
    """
    
    try:
        # 执行查询，传递limit参数
        df = fetch_df(sql, codes=tuple(codes), limit=limit)
        
        # 对于1W和1M周期，需要特殊处理以获取正确的聚合数据
        if interval == "1W" and not df.empty:
            # 对于周线数据，需要重新查询并聚合最近一周的数据
            all_weekly_data = []
            for code in codes:
                # 对于每个代码，查询最近的完整周数据
                weekly_sql = """
                SELECT 
                    MIN(datetime) as datetime,
                    code,
                    FIRST(open) as open,
                    MAX(high) as high,
                    MIN(low) as low,
                    LAST(close) as close,
                    SUM(volume) as volume
                FROM 
                    day_realtime
                WHERE 
                    code = :code
                GROUP BY 
                    code,
                    strftime('%Y-%W', datetime)
                ORDER BY 
                    datetime DESC
                LIMIT 1
                """
                weekly_df = fetch_df(weekly_sql, code=code)
                if not weekly_df.empty:
                    all_weekly_data.append(weekly_df)
            
            if all_weekly_data:
                df = pd.concat(all_weekly_data, ignore_index=True)
        elif interval == "1M" and not df.empty:
            # 对于月线数据，需要重新查询并聚合最近一月的数据
            all_monthly_data = []
            for code in codes:
                # 对于每个代码，查询最近的完整月数据
                monthly_sql = """
                SELECT 
                    MIN(datetime) as datetime,
                    code,
                    FIRST(open) as open,
                    MAX(high) as high,
                    MIN(low) as low,
                    LAST(close) as close,
                    SUM(volume) as volume
                FROM 
                    day_realtime
                WHERE 
                    code = :code
                GROUP BY 
                    code,
                    strftime('%Y-%m', datetime)
                ORDER BY 
                    datetime DESC
                LIMIT 1
                """
                monthly_df = fetch_df(monthly_sql, code=code)
                if not monthly_df.empty:
                    all_monthly_data.append(monthly_df)
            
            if all_monthly_data:
                df = pd.concat(all_monthly_data, ignore_index=True)
        else:
            # 对于其他周期，直接使用aggregate_kline_data函数进行聚合处理
            # 注意：interval映射逻辑已移至aggregate_kline_data函数内部实现
            df = aggregate_kline_data(df, interval)
        
        # 记录返回结果的基本信息
        if not df.empty:
            # 按代码分组，记录每个代码的时间范围
            code_time_ranges = []
            for code, group in df.groupby('code'):
                min_time = group['datetime'].min()
                max_time = group['datetime'].max()
                code_time_ranges.append(f"{code}: [{min_time}, {max_time}]")
            
            logger.info(f"批量查询结果: total_rows={len(df)}, total_columns={len(df.columns)}, code_time_ranges={', '.join(code_time_ranges)}")
        else:
            logger.info("批量查询结果: 空DataFrame")
        
        return df
    except Exception as e:
        logger.error(f"批量获取K线数据失败: {e}")
        return pd.DataFrame()

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
