import os
import redis
import json
import socket
from functools import wraps
from typing import Any, Callable, Optional, Dict, Tuple, List
import hashlib
import time
import logging
import os
import yaml
import concurrent.futures

# 配置日志
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 加载数据库配置
def load_db_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载数据库配置，包括Redis配置
    优先级：参数 > 环境变量 DB_CONFIG > 默认路径
    """
    path = config_path or os.environ.get("DB_CONFIG", "config/db_config.yaml")
    
    # 确保配置文件路径是绝对路径
    if not os.path.isabs(path):
        # 获取项目根目录
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        # 构建相对于项目根目录的绝对路径
        path = os.path.join(current_dir, "backend", path)
    
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    
    return raw

# 加载配置
_config = load_db_config()

# Redis配置 - 从配置文件获取，环境变量覆盖
REDIS_HOST = os.environ.get('REDIS_HOST', _config.get('redis', {}).get('host', 'localhost'))
REDIS_PORT = int(os.environ.get('REDIS_PORT', _config.get('redis', {}).get('port', 6379)))
REDIS_DB = int(os.environ.get('REDIS_DB', _config.get('redis', {}).get('db', 0)))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', _config.get('redis', {}).get('password', ''))

# Redis连接管理类
class RedisManager:
    def __init__(self):
        self.client = None
        self.is_redis_available = False
        self.last_connection_attempt = 0
        self.retry_interval = 30  # 连接重试间隔，单位：秒
        self.connect()
    
    def connect(self):
        try:
            # 配置Redis连接池 - 增强稳定性配置
            pool_params = {
                'host': REDIS_HOST,
                'port': REDIS_PORT,
                'db': REDIS_DB,
                'decode_responses': True,
                'socket_timeout': 10,  # 增加超时时间
                'socket_keepalive': True,
                'socket_keepalive_options': {
                    socket.TCP_KEEPIDLE: 60,
                    socket.TCP_KEEPINTVL: 10,
                    socket.TCP_KEEPCNT: 5
                },
                'retry_on_timeout': True,
                'health_check_interval': 15,  # 更频繁的健康检查
                'max_connections': 50,  # 连接池大小
                'socket_connect_timeout': 5,  # 增加连接超时时间
                'tcp_keepalive': True
            }
            
            # 如果设置了密码，则添加密码参数
            if REDIS_PASSWORD:
                pool_params['password'] = REDIS_PASSWORD
                
            pool = redis.ConnectionPool(**pool_params)
            self.client = redis.Redis(connection_pool=pool)
            self.client.ping()
            self.is_redis_available = True
            logger.info(f"Redis连接成功: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
        except Exception as e:
            self.client = {}
            self.is_redis_available = False
            logger.warning(f"Redis连接失败，将使用内存缓存: {e}")
    
    def get_client(self):
        # 如果Redis之前连接失败，在指定间隔后尝试重新连接
        if not self.is_redis_available and isinstance(self.client, dict):
            current_time = time.time()
            if current_time - self.last_connection_attempt >= self.retry_interval:
                self.last_connection_attempt = current_time
                self.connect()
        return self.client

# 使用单例模式
_redis_manager = RedisManager()
_redis_client = _redis_manager.get_client()

# Redis操作装饰器 - 添加重试逻辑
def redis_operation_with_retry(max_retries=3, retry_delay=0.5):
    """
    Redis操作重试装饰器，针对连接重置等临时性错误提供重试机制
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            retry_count = 0
            last_error = None
            
            while retry_count <= max_retries:
                try:
                    return func(self, *args, **kwargs)
                except redis.RedisError as e:
                    error_code = str(e).split()[0] if str(e).split() else ""
                    # 特定错误类型才重试（连接重置、超时等）
                    if any(err in str(e).lower() for err in ['connection reset by peer', 'timed out', 'error 104', 'error -2']):
                        retry_count += 1
                        last_error = e
                        if retry_count <= max_retries:
                            logger.warning(f"Redis操作失败，尝试重试({retry_count}/{max_retries}): {e}")
                            time.sleep(retry_delay * (2 ** (retry_count - 1)))  # 指数退避
                        else:
                            logger.error(f"Redis操作重试失败({max_retries}次): {e}")
                            # 更新Redis连接状态
                            if hasattr(_redis_manager, 'is_redis_available'):
                                _redis_manager.is_redis_available = False
                            # 尝试重新连接
                            _redis_manager.connect()
                            # 如果仍然失败，使用内存缓存
                            if not _redis_manager.is_redis_available:
                                logger.warning("Redis连接不可用，将使用内存缓存")
                                raise e
                    else:
                        # 非临时性错误，直接抛出
                        logger.error(f"Redis操作错误: {e}")
                        raise e
            
            # 所有重试都失败，抛出最后一个错误
            raise last_error
        return wrapper
    return decorator

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
    @redis_operation_with_retry(max_retries=3)
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
    @redis_operation_with_retry(max_retries=3)
    def set(key: str, value: Any, expire_time: int = DEFAULT_EXPIRE_TIME) -> None:
        """设置缓存数据，处理各种不可JSON序列化类型，特别是datetime对象"""
        # 获取最新的客户端实例
        client = _redis_manager.get_client()
        
        if isinstance(client, dict):
            # 使用内存字典
            client[key] = ({'value': value, '_expire_time': expire_time}, time.time())
        else:
            # 使用Redis，需要序列化数据
            try:
                # 第一次尝试：直接序列化
                client.setex(key, expire_time, json.dumps(value))
            except (TypeError, OverflowError) as e:
                # 第一次失败：使用_process_serialization_types处理
                try:
                    processed_value = CacheService._process_serialization_types(value)
                    client.setex(key, expire_time, json.dumps(processed_value))
                except Exception as process_error:
                    # 第二次失败：使用自定义JSON编码器处理所有datetime类型
                    try:
                        from datetime import datetime, date, time as datetime_time
                        import pandas as pd
                        
                        class CustomJSONEncoder(json.JSONEncoder):
                            def default(self, obj):
                                if isinstance(obj, (datetime, date, datetime_time)):
                                    return obj.isoformat()
                                elif isinstance(obj, pd.Timestamp):
                                    return obj.isoformat()
                                elif hasattr(obj, 'to_dict'):
                                    return obj.to_dict()
                                else:
                                    try:
                                        return str(obj)
                                    except:
                                        return "[Unserializable]"
                                        
                        encoded_value = json.dumps(value, cls=CustomJSONEncoder)
                        client.setex(key, expire_time, encoded_value)
                    except Exception as encoder_error:
                        # 第三次失败：作为最后的尝试，转换为字符串
                        try:
                            client.setex(key, expire_time, json.dumps(str(value)))
                        except Exception:
                            # 所有尝试都失败，记录详细错误信息
                            error_msg = f"缓存设置彻底失败: {key}, 原始错误: {str(e)}, 处理后错误: {str(process_error)}, 编码器错误: {str(encoder_error)}"
                            logger.error(error_msg)
                            # 可以选择将错误存储到一个特殊的缓存键中，以便后续调试
                            try:
                                error_key = f"error:{key}"
                                error_info = {"original_error": str(e), "process_error": str(process_error), "encoder_error": str(encoder_error)}
                                client.setex(error_key, 60 * 60, json.dumps(error_info))
                            except:
                                pass
                    
    @staticmethod
    def _process_serialization_types(data):
        """递归处理数据中的不可JSON序列化类型，包括datetime、pandas Timestamp等"""
        import pandas as pd
        import numpy as np
        from datetime import datetime, date, timedelta
        
        # 处理Python标准库的datetime和date对象
        if isinstance(data, (datetime, date)):
            return data.isoformat()
        # 处理timedelta对象
        elif isinstance(data, timedelta):
            return str(data)
        # 处理pandas Timestamp对象
        elif isinstance(data, pd.Timestamp):
            return data.isoformat()
        # 处理pandas Series
        elif isinstance(data, pd.core.series.Series):
            return data.tolist()
        # 处理numpy数组
        elif isinstance(data, np.ndarray):
            return data.tolist()
        # 处理numpy数值类型
        elif isinstance(data, np.number):
            return data.item()
        # 处理numpy日期时间类型
        elif isinstance(data, np.datetime64):
            # 转换为Python datetime并序列化
            return pd.Timestamp(data).isoformat()
        # 处理字典
        elif isinstance(data, dict):
            # 递归处理字典中的每个值
            processed_dict = {}
            for k, v in data.items():
                # 确保键也是可序列化的
                processed_key = str(k) if not isinstance(k, (str, int, float, bool, type(None))) else k
                processed_dict[processed_key] = CacheService._process_serialization_types(v)
            return processed_dict
        # 处理列表
        elif isinstance(data, list):
            # 递归处理列表中的每个元素
            return [CacheService._process_serialization_types(item) for item in data]
        # 处理元组
        elif isinstance(data, tuple):
            # 递归处理元组中的每个元素
            return tuple(CacheService._process_serialization_types(item) for item in data)
        # 处理集合
        elif isinstance(data, set):
            # 转换为列表并递归处理
            return [CacheService._process_serialization_types(item) for item in data]
        # 处理字符串类型
        elif isinstance(data, str):
            # 字符串已经是可序列化的，直接返回
            return data
        # 处理其他不可JSON序列化的类型
        else:
            # 尝试使用str()转换为字符串
            try:
                return str(data)
            except Exception:
                # 如果转换失败，返回一个占位符
                return "[Unserializable Object]"

    @staticmethod
    @redis_operation_with_retry(max_retries=3)
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
    @redis_operation_with_retry(max_retries=3)
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
    """优化的DataFrame序列化函数，处理datetime列和数值类型"""
    # 避免不必要的副本
    if df.empty:
        return []
    
    # 创建DataFrame的副本以避免修改原始数据
    processed_df = df.copy()
    
    # 转换DataFrame为字典列表，使用更高效的方式
    records = []
    
    # 预计算所有列名和数据类型
    columns = processed_df.columns.tolist()
    dtypes = processed_df.dtypes
    
    # 预先处理datetime列的转换
    datetime_columns = [col for col in columns if pd.api.types.is_datetime64_any_dtype(dtypes[col])]
    # 识别数值列，特别是价格相关列
    numeric_columns = [col for col in columns if pd.api.types.is_numeric_dtype(dtypes[col])]
    price_columns = ['open', 'high', 'low', 'close', 'volume']
    
    # 批量获取数据并处理
    for row in processed_df.itertuples(index=False, name=None):
        record = {}
        for i, col in enumerate(columns):
            value = row[i]
            # 处理datetime类型，使用ISO格式以确保与反序列化兼容
            if col in datetime_columns:
                if pd.notna(value):
                    record[col] = value.strftime('%Y-%m-%dT%H:%M:%S')
                else:
                    record[col] = None
            # 处理数值类型，特别是价格相关列，确保None值被正确处理
            elif col in numeric_columns:
                # 特殊处理价格相关列，确保即使是0也能正确序列化
                if pd.notna(value):
                    # 转换为基本数值类型
                    if isinstance(value, np.integer):
                        record[col] = int(value)
                    elif isinstance(value, np.floating):
                        record[col] = float(value)
                    else:
                        record[col] = value
                else:
                    record[col] = 0 if col in price_columns else None
            # 处理字符串列
            elif pd.api.types.is_string_dtype(dtypes[col]):
                if pd.notna(value):
                    record[col] = str(value)
                else:
                    record[col] = ''
            # 处理其他类型
            else:
                if pd.notna(value):
                    record[col] = value
                else:
                    record[col] = None
        records.append(record)
    
    return records

# 优化的DataFrame反序列化函数
def deserialize_to_dataframe(data: List[Dict]) -> pd.DataFrame:
    """优化的DataFrame反序列化函数，处理datetime列和数值类型，确保空值被正确处理"""
    if not data:
        return pd.DataFrame()
    
    # 快速创建DataFrame
    df = pd.DataFrame(data)
    
    # 预定义价格相关列，确保它们被正确处理
    price_columns = ['open', 'high', 'low', 'close', 'volume']
    
    # 批量检测和转换datetime列，优化性能
    datetime_columns = []
    numeric_columns = []
    
    # 提前识别可能的datetime列和数值列
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                # 仅转换非空值，减少不必要的处理
                mask = pd.notna(df[col])
                if mask.any():
                    # 尝试转换前10个非空值作为测试，避免全量检查
                    sample_size = min(10, mask.sum())
                    sample_values = df.loc[mask, col].iloc[:sample_size]
                    
                    # 检查是否是datetime列
                    if all(isinstance(val, str) and (('-' in val and ':' in val) or len(val) >= 8) for val in sample_values):
                        datetime_columns.append(col)
                    # 检查是否是数值列
                    elif all(isinstance(val, (int, float)) or (
                            isinstance(val, str) and val.replace('.', '', 1).isdigit()
                        ) for val in sample_values):
                        numeric_columns.append(col)
            except Exception:
                continue
    
    # 确保价格相关列被添加到数值列列表中
    for col in price_columns:
        if col in df.columns and col not in numeric_columns:
            numeric_columns.append(col)
    
    # 批量转换已识别的datetime列
    if datetime_columns:
        for col in datetime_columns:
            try:
                mask = pd.notna(df[col])
                if mask.any():
                    # 指定常见的日期时间格式，避免格式推断警告
                    try:
                        # 尝试ISO格式 (YYYY-MM-DDTHH:MM:SS)
                        df.loc[mask, col] = pd.to_datetime(df.loc[mask, col], format='%Y-%m-%dT%H:%M:%S', errors='coerce')
                    except:
                        try:
                            # 尝试日期格式 (YYYY-MM-DD)
                            df.loc[mask, col] = pd.to_datetime(df.loc[mask, col], format='%Y-%m-%d', errors='coerce')
                        except:
                            # 尝试其他常见格式
                            df.loc[mask, col] = pd.to_datetime(df.loc[mask, col], errors='coerce')
            except Exception:
                # 如果转换失败，保持原数据类型
                continue
    
    # 批量转换已识别的数值列，特别是价格相关列
    if numeric_columns:
        for col in numeric_columns:
            try:
                # 特殊处理价格相关列，确保即使是空字符串也能正确转换
                if col in price_columns:
                    # 先将空字符串和None替换为NaN
                    df[col] = df[col].replace({ '': np.nan, None: np.nan })
                    # 然后转换为数值类型
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    # 价格字段应该有实际数值，避免0值被错误处理
                    # 如果有全0值，可能是数据问题，但我们不做特殊处理
                else:
                    # 其他数值列正常处理
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            except Exception as e:
                # 添加日志以便调试
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"转换列 {col} 为数值类型时出错: {e}")
                # 如果转换失败，保持原数据类型
                continue
    
    # 确保所有列中的None值被正确处理，不会变成"NaT"
    for col in df.columns:
        # 替换空字符串为空值（非价格列）
        if df[col].dtype == 'object' and col not in price_columns:
            df[col] = df[col].replace('', None)
        # 确保datetime列中的空值正确处理
        elif pd.api.types.is_datetime64_any_dtype(df[col].dtype):
            # 不做特殊处理，因为pandas会自动处理NaT
            pass
        # 确保数值列中的空值正确处理
        elif pd.api.types.is_numeric_dtype(df[col].dtype):
            # 不做特殊处理，因为pandas会自动处理NaN
            pass
    
    return df


def cache_dataframe_result(expire_time: int = DEFAULT_EXPIRE_TIME):
    """缓存pandas DataFrame结果的装饰器，支持多种返回格式"""
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
                        # 记录反序列化后DataFrame的信息
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Deserialized DataFrame shape: {df.shape}")
                            logger.debug(f"Deserialized DataFrame columns: {list(df.columns)}")
                            if not df.empty:
                                logger.debug(f"Deserialized DataFrame preview: {df.head(2).to_dict('records')}")
                        
                        # 检查是否包含query_params
                        if 'query_params' in result_dict:
                            if result_dict.get('is_paginated', False):
                                # 返回3元素元组 (df, total_count, query_params)
                                return df, result_dict['total_count'], result_dict['query_params']
                            else:
                                # 返回2元素元组 (df, query_params)
                                return df, result_dict['query_params']
                        else:
                            # 返回2元素元组 (df, total_count)
                            return df, result_dict['total_count']
                    else:
                        # 非分页结果处理
                        df = deserialize_to_dataframe(result_dict)
                        # 记录反序列化后DataFrame的信息
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Deserialized DataFrame shape: {df.shape}")
                            logger.debug(f"Deserialized DataFrame columns: {list(df.columns)}")
                            if not df.empty:
                                logger.debug(f"Deserialized DataFrame preview: {df.head(2).to_dict('records')}")
                        return df
                except Exception as e:
                    logger.error(f"缓存数据解析失败: {func.__name__}, 错误: {e}")
                    # 如果解析失败，继续执行原函数获取结果
            
            # 缓存未命中或解析失败，执行函数获取结果
            result = func(*args, **kwargs)

            # 缓存结果，处理DataFrame或元组(分页结果)
            try:
                # 准备要缓存的数据
                data_to_cache = None
                df = None
                
                # 检查是否是分页结果（元组形式）
                if isinstance(result, tuple):
                    # 处理3元素元组 (df, total_count, query_params)
                    if len(result) == 3 and hasattr(result[0], 'to_dict'):
                        df, total_count, query_params = result
                        # 优化的序列化处理
                        data_to_cache = {
                            'is_paginated': True,
                            'data': serialize_dataframe(df),
                            'total_count': total_count,
                            'query_params': CacheService._process_serialization_types(query_params)
                        }
                    # 处理2元素元组 (df, total_count) 或 (df, query_params)
                    elif len(result) == 2 and hasattr(result[0], 'to_dict'):
                        df = result[0]
                        if isinstance(result[1], int):
                            # 分页结果 (df, total_count)
                            total_count = result[1]
                            data_to_cache = {
                                'is_paginated': True,
                                'data': serialize_dataframe(df),
                                'total_count': total_count
                            }
                        else:
                            # 非分页结果但包含query_params (df, query_params)
                            query_params = result[1]
                            data_to_cache = {
                                'is_paginated': False,
                                'data': serialize_dataframe(df),
                                'query_params': CacheService._process_serialization_types(query_params)
                            }
                elif result is not None and hasattr(result, 'to_dict'):
                    # 非分页结果处理
                    df = result
                    # 优化的序列化处理
                    data_to_cache = serialize_dataframe(df)
                
                # 记录要序列化的DataFrame信息
                if df is not None and logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"DataFrame to serialize shape: {df.shape}")
                    logger.debug(f"DataFrame to serialize columns: {list(df.columns)}")
                    if not df.empty:
                        logger.debug(f"DataFrame to serialize preview: {df.head(2).to_dict('records')}")
                
                # 设置缓存
                if data_to_cache is not None:
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
        try:
            await asyncio.wait_for(
                loop.run_in_executor(executor, CacheService.set, key, data, expire_time),
                timeout=10
            )
        except Exception as e:
            logger.error(f"异步缓存设置失败: {key}, 错误: {str(e)}")

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