import os
import redis
import json
from functools import wraps
from typing import Any, Callable, Optional, Dict, Tuple, List
import hashlib
import time
import logging
import os
import concurrent.futures

# 配置日志
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Redis配置
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))

# Redis连接管理类
class RedisManager:
    def __init__(self):
        self.client = None
        self.is_redis_available = False
        self.connect()
    
    def connect(self):
        try:
            # 配置Redis连接池
            pool = redis.ConnectionPool(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
                socket_keepalive=True,
                retry_on_timeout=True,
                health_check_interval=30,
                max_connections=50,  # 连接池大小
                socket_connect_timeout=3  # 连接超时时间
            )
            self.client = redis.Redis(connection_pool=pool)
            self.client.ping()
            self.is_redis_available = True
            # Redis连接成功的信息已省略，以减少日志输出
        except Exception as e:
            self.client = {}
            self.is_redis_available = False
            logger.error(f"Redis连接失败，将使用内存缓存: {e}")
    
    def get_client(self):
        # 如果Redis之前连接失败，尝试重新连接
        if not self.is_redis_available and isinstance(self.client, dict):
            self.connect()
        return self.client

# 使用单例模式
_redis_manager = RedisManager()
_redis_client = _redis_manager.get_client()

# 默认过期时间（秒）
DEFAULT_EXPIRE_TIME = 60 * 5  # 5分钟
LONG_EXPIRE_TIME = 60 * 60 * 24  # 24小时

# 缓存命中统计
cache_metrics = {
    'total': 0,
    'hits': 0,
    'misses': 0,
    'ttl_renewed': 0
}

# 获取缓存统计信息
def get_cache_metrics() -> Dict[str, int]:
    """获取缓存统计信息"""
    with_metrics = cache_metrics.copy()
    if with_metrics['total'] > 0:
        with_metrics['hit_rate'] = round((with_metrics['hits'] / with_metrics['total']) * 100, 2)
    else:
        with_metrics['hit_rate'] = 0
    return with_metrics

# 重置缓存统计
def reset_cache_metrics():
    """重置缓存统计"""
    global cache_metrics
    cache_metrics = {
        'total': 0,
        'hits': 0,
        'misses': 0,
        'ttl_renewed': 0
    }

class CacheService:
    @staticmethod
    def _generate_key(func_name: str, *args, **kwargs) -> str:
        """生成缓存键名"""
        # 排除不可哈希的参数
        hashable_kwargs = {k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool, type(None))) and not isinstance(v, Callable)}
        key_parts = [func_name] + [str(arg) for arg in args] + [f"{k}={v}" for k, v in sorted(hashable_kwargs.items())]
        key_str = "|" + "|_".join(key_parts)
        # 使用MD5哈希确保键名长度合理
        return hashlib.md5(key_str.encode()).hexdigest()

    @staticmethod
    def get(key: str) -> Optional[Any]:
        """从缓存获取数据"""
        cache_metrics['total'] += 1
        
        # 获取最新的客户端实例
        client = _redis_manager.get_client()
        
        if isinstance(client, dict):
            # 使用内存字典
            if key in client:
                cache_metrics['hits'] += 1
                data, timestamp = client[key]
                # 检查是否过期
                if time.time() - timestamp < data.get('_expire_time', float('inf')):
                    # 更新过期时间
                    client[key] = (data, time.time())
                    cache_metrics['ttl_renewed'] += 1
                    return data.get('value')
                else:
                    # 删除过期数据
                    del client[key]
            cache_metrics['misses'] += 1
            return None
        else:
            # 使用Redis
            data = client.get(key)
            if data:
                cache_metrics['hits'] += 1
                # 重新设置TTL，实现热点数据缓存延长
                client.expire(key, LONG_EXPIRE_TIME)
                cache_metrics['ttl_renewed'] += 1
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return None
            cache_metrics['misses'] += 1
            return None

    @staticmethod
    def set(key: str, value: Any, expire_time: int = DEFAULT_EXPIRE_TIME) -> None:
        """设置缓存数据，处理Timestamp对象的序列化"""
        # 获取最新的客户端实例
        client = _redis_manager.get_client()
        
        if isinstance(client, dict):
            # 使用内存字典
            client[key] = ({'value': value, '_expire_time': expire_time}, time.time())
        else:
            # 使用Redis，需要序列化数据
            try:
                # 尝试直接序列化
                client.setex(key, expire_time, json.dumps(value))
            except TypeError as e:
                # 检查是否是Timestamp对象导致的序列化错误
                if 'Timestamp' in str(e):
                    # 处理包含Timestamp对象的数据
                    processed_value = CacheService._process_serialization_types(value)
                    client.setex(key, expire_time, json.dumps(processed_value))
                else:
                    # 其他类型错误直接抛出
                    raise
                    
    @staticmethod
    def _process_serialization_types(data):
        """递归处理数据中的不可JSON序列化类型，特别是pandas Timestamp"""
        import pandas as pd
        import numpy as np
        
        if isinstance(data, pd.Timestamp):
            # 处理pandas Timestamp对象
            return data.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(data, pd.core.series.Series):
            # 处理pandas Series
            return data.tolist()
        elif isinstance(data, np.ndarray):
            # 处理numpy数组
            return data.tolist()
        elif isinstance(data, np.number):
            # 处理numpy数值类型
            return data.item()
        elif isinstance(data, dict):
            # 递归处理字典
            return {k: CacheService._process_serialization_types(v) for k, v in data.items()}
        elif isinstance(data, list):
            # 递归处理列表
            return [CacheService._process_serialization_types(item) for item in data]
        elif isinstance(data, tuple):
            # 递归处理元组
            return tuple(CacheService._process_serialization_types(item) for item in data)
        else:
            # 其他类型保持不变
            return data

    @staticmethod
    def delete(key: str) -> None:
        """删除缓存数据"""
        # 获取最新的客户端实例
        client = _redis_manager.get_client()
        
        if isinstance(client, dict):
            if key in client:
                del client[key]
        else:
            client.delete(key)

    @staticmethod
    def clear(pattern: str = '*') -> None:
        """清除匹配模式的缓存"""
        # 获取最新的客户端实例
        client = _redis_manager.get_client()
        
        if isinstance(client, dict):
            if pattern == '*':
                client.clear()
            else:
                # 简单的模式匹配实现
                keys_to_delete = [key for key in client if pattern in key]
                for key in keys_to_delete:
                    del client[key]
        else:
            for key in client.keys(pattern):
                client.delete(key)

# 创建缓存装饰器
def cache_result(expire_time: int = DEFAULT_EXPIRE_TIME):
    """缓存函数结果的装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键，包含所有参数（包括分页参数）
            key = CacheService._generate_key(func.__name__, *args, **kwargs)
            
            # 尝试从缓存获取结果
            result = CacheService.get(key)
            if result is not None:
                # 缓存命中
                return result
            
            # 缓存未命中，执行函数
            result = func(*args, **kwargs)
            
            # 缓存结果
            CacheService.set(key, result, expire_time)
            
            return result
        return wrapper
    return decorator

# 针对pandas DataFrame的特殊处理
import pandas as pd

# 优化的DataFrame序列化函数
import pandas as pd
import numpy as np
def serialize_dataframe(df: pd.DataFrame) -> List[Dict]:
    """优化的DataFrame序列化函数，处理datetime列"""
    # 避免不必要的副本
    if df.empty:
        return []
    
    # 转换DataFrame为字典列表，使用更高效的方式
    records = []
    
    # 预计算所有列名和数据类型
    columns = df.columns.tolist()
    dtypes = df.dtypes
    
    # 预先处理datetime列的转换
    datetime_columns = [col for col in columns if pd.api.types.is_datetime64_any_dtype(dtypes[col])]
    
    # 批量获取数据并处理
    for row in df.itertuples(index=False, name=None):
        record = {}
        for i, col in enumerate(columns):
            value = row[i]
            # 处理datetime类型
            if col in datetime_columns:
                if pd.notna(value):
                    record[col] = value.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    record[col] = None
            # 处理numpy类型
            elif isinstance(value, np.integer):
                record[col] = int(value)
            elif isinstance(value, np.floating):
                record[col] = float(value)
            # 处理其他类型
            else:
                record[col] = value
        records.append(record)
    
    return records

# 优化的DataFrame反序列化函数
def deserialize_to_dataframe(data: List[Dict]) -> pd.DataFrame:
    """优化的DataFrame反序列化函数，处理datetime列，提升日线图和分时图数据处理效率"""
    if not data:
        return pd.DataFrame()
    
    # 快速创建DataFrame
    df = pd.DataFrame(data)
    
    # 批量检测和转换datetime列，优化性能
    datetime_columns = []
    
    # 提前识别可能的datetime列
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                # 仅转换非空值，减少不必要的处理
                mask = pd.notna(df[col])
                if mask.any():
                    # 尝试转换前10个非空值作为测试，避免全量检查
                    sample_size = min(10, mask.sum())
                    sample_values = df.loc[mask, col].iloc[:sample_size]
                    if all(isinstance(val, str) and (('-' in val and ':' in val) or len(val) >= 8) for val in sample_values):
                        datetime_columns.append(col)
            except Exception:
                continue
    
    # 批量转换已识别的datetime列
    if datetime_columns:
        for col in datetime_columns:
            try:
                mask = pd.notna(df[col])
                if mask.any():
                    # 移除已弃用的参数，使用默认的严格模式
                    df.loc[mask, col] = pd.to_datetime(df.loc[mask, col], errors='coerce')
            except Exception:
                # 如果转换失败，保持原数据类型
                continue
    
    return df


def cache_dataframe_result(expire_time: int = DEFAULT_EXPIRE_TIME):
    """缓存pandas DataFrame结果的装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键，包含所有参数（包括分页参数）
            key = CacheService._generate_key(f"df_{func.__name__}", *args, **kwargs)
            
            # 尝试从缓存获取结果
            result_dict = CacheService.get(key)
            
            if result_dict is not None:
                # 缓存命中，将字典转回DataFrame或元组(如果是分页结果)
                try:
                    # 检查是否是分页结果（元组形式）
                    if isinstance(result_dict, dict) and 'is_paginated' in result_dict:
                        # 分页结果处理
                        df = deserialize_to_dataframe(result_dict['data'])
                        return df, result_dict['total_count']
                    else:
                        # 非分页结果处理
                        df = deserialize_to_dataframe(result_dict)
                        return df
                except Exception as e:
                    logger.error(f"缓存数据解析失败: {func.__name__}, 错误: {e}")
                    # 如果解析失败，继续执行原函数获取结果
            
            # 缓存未命中或解析失败，执行函数获取结果
            result = func(*args, **kwargs)

            # 缓存结果，处理DataFrame或元组(分页结果)
            try:
                # 检查是否是分页结果（元组形式）
                if isinstance(result, tuple) and len(result) == 2 and hasattr(result[0], 'to_dict'):
                    df, total_count = result
                    # 优化的序列化处理
                    data_to_cache = {
                        'is_paginated': True,
                        'data': serialize_dataframe(df),
                        'total_count': total_count
                    }
                    CacheService.set(key, data_to_cache, expire_time)
                elif result is not None and hasattr(result, 'to_dict'):
                    # 非分页结果处理
                    # 优化的序列化处理
                    data_to_cache = serialize_dataframe(result)
                    CacheService.set(key, data_to_cache, expire_time)
            except Exception as e:
                logger.error(f"缓存设置失败: {func.__name__}, 错误: {e}")
                # 即使缓存设置失败，也返回函数结果
                
            return result
        return wrapper
    return decorator

# 行情数据特定的缓存键生成函数
def get_market_data_key(code: str, start: str, end: str, interval: str = '1m') -> str:
    """生成行情数据的缓存键"""
    return f"market:{code}:{interval}:{start}:{end}"

# 清除特定代码的行情数据缓存
def clear_market_data_cache(code: str = None) -> None:
    """清除行情数据缓存"""
    if code:
        CacheService.clear(f"market:{code}:*")
    else:
        CacheService.clear("market:*")

# 批量设置行情数据缓存
def set_market_data_cache(code: str, start: str, end: str, data: Any, interval: str = '1m', expire_time: int = DEFAULT_EXPIRE_TIME) -> None:
    """设置行情数据缓存"""
    key = get_market_data_key(code, start, end, interval)
    CacheService.set(key, data, expire_time)

# 获取行情数据缓存
def get_market_data_cache(code: str, start: str, end: str, interval: str = '1m') -> Optional[Any]:
    """获取行情数据缓存"""
    key = get_market_data_key(code, start, end, interval)
    return CacheService.get(key)

# 异步版本的缓存装饰器
import asyncio
from functools import wraps

# 优化的异步缓存设置函数
async def async_set_cache_background(key: str, data: Any, expire_time: int = DEFAULT_EXPIRE_TIME):
    """在单独的线程中处理缓存设置，避免阻塞事件循环，提升大量数据处理效率"""
    loop = asyncio.get_running_loop()
    # 使用自定义线程池配置优化大数据量处理
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # 使用超时机制确保不会长时间阻塞
        await asyncio.wait_for(
            loop.run_in_executor(executor, CacheService.set, key, data, expire_time),
            timeout=10
        )

# 异步缓存设置函数
def async_cache_set(key: str, value: Any, expire_time: int = DEFAULT_EXPIRE_TIME) -> None:
    """异步设置缓存数据，使用线程池优化性能"""
    # 使用线程池避免阻塞事件循环
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(CacheService.set, key, value, expire_time)
        try:
            # 设置超时以避免长时间阻塞
            future.result(timeout=5)
        except Exception as e:
            logger.error(f"异步缓存设置失败: {e}")

# 异步缓存装饰器
def async_cache_result(expire_time: int = DEFAULT_EXPIRE_TIME):
    """异步缓存函数结果的装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键，包含所有参数
            key = CacheService._generate_key(f"async_{func.__name__}", *args, **kwargs)
            
            # 尝试从缓存获取结果
            result = CacheService.get(key)
            if result is not None:
                # 缓存命中
                return result
            
            # 缓存未命中，异步执行函数
            result = await func(*args, **kwargs)
            
            # 缓存结果（优化的异步处理，不阻塞主流程）
            asyncio.create_task(async_set_cache_background(key, result, expire_time))
            
            return result
        return wrapper
    return decorator

# 异步DataFrame缓存装饰器
def async_cache_dataframe_result(expire_time: int = DEFAULT_EXPIRE_TIME):
    """异步缓存pandas DataFrame结果的装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键，包含所有参数
            key = CacheService._generate_key(f"async_df_{func.__name__}", *args, **kwargs)
            
            # 尝试从缓存获取结果
            result_dict = CacheService.get(key)
            
            if result_dict is not None:
                # 缓存命中，将字典转回DataFrame或元组(如果是分页结果)
                try:
                    # 检查是否是分页结果（元组形式）
                    if isinstance(result_dict, dict) and 'is_paginated' in result_dict:
                        # 分页结果处理
                        df = deserialize_to_dataframe(result_dict['data'])
                        return df, result_dict['total_count']
                    else:
                        # 非分页结果处理
                        df = deserialize_to_dataframe(result_dict)
                        return df
                except Exception as e:
                    logger.error(f"缓存数据解析失败: {func.__name__}, 错误: {e}")
                    # 如果解析失败，继续执行原函数获取结果
            
            # 缓存未命中或解析失败，异步执行函数获取结果
            result = await func(*args, **kwargs)

            # 异步缓存结果，处理DataFrame或元组(分页结果)
            try:
                # 准备要缓存的数据
                data_to_cache = None
                
                # 检查是否是分页结果（元组形式）
                if isinstance(result, tuple) and len(result) == 2 and hasattr(result[0], 'to_dict'):
                    df, total_count = result
                    # 优化的序列化处理
                    data_to_cache = {
                        'is_paginated': True,
                        'data': serialize_dataframe(df),
                        'total_count': total_count
                    }
                elif result is not None and hasattr(result, 'to_dict'):
                    # 非分页结果处理
                    # 优化的序列化处理
                    data_to_cache = serialize_dataframe(result)
                
                if data_to_cache is not None:
                    # 异步设置缓存，不阻塞主流程（使用优化的异步缓存设置）
                    asyncio.create_task(async_set_cache_background(key, data_to_cache, expire_time))
            except Exception as e:
                logger.error(f"缓存设置失败: {func.__name__}, 错误: {e}")
                # 即使缓存设置失败，也返回函数结果
                
            return result
        return wrapper
    return decorator

# 异步版本的行情数据缓存函数
async def async_clear_market_data_cache(code: str = None) -> None:
    """异步清除行情数据缓存"""
    # 简单包装同步方法，使其可以在异步任务中运行
    clear_market_data_cache(code)

async def async_update_market_data_and_refresh_cache(data, table_name, code=None):
    """异步更新市场数据并刷新相关缓存"""
    from ..db import to_sql_async
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # 异步写入数据到数据库
        await to_sql_async(data, table_name)
        # 成功更新市场数据到表的信息已省略，以减少日志输出
        
        # 异步刷新相关缓存
        await async_clear_market_data_cache(code)
        # 成功刷新市场数据缓存的信息已省略，以减少日志输出
        
        return True
    except Exception as e:
        logger.error(f"更新市场数据失败: {e}")
        return False