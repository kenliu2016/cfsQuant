import os
import redis
import json
from functools import wraps
from typing import Any, Callable, Optional, Dict, Tuple
import hashlib
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Redis配置
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))

# 尝试连接Redis，如果连接失败则使用内存缓存作为降级方案
_redis_client = None
try:
    _redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_timeout=5  # 设置连接超时时间
    )
    # 测试连接
    _redis_client.ping()
    logger.info("Redis连接成功")
except Exception as e:
    logger.error(f"Redis连接失败，将使用内存缓存: {e}")
    # 使用内存字典作为降级方案
    _redis_client = {}

# 默认过期时间（秒）
DEFAULT_EXPIRE_TIME = 60 * 5  # 5分钟
LONG_EXPIRE_TIME = 60 * 60 * 24  # 24小时

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
        if isinstance(_redis_client, dict):
            # 使用内存字典
            if key in _redis_client:
                data, timestamp = _redis_client[key]
                # 检查是否过期
                if time.time() - timestamp < data.get('_expire_time', float('inf')):
                    return data.get('value')
                else:
                    # 删除过期数据
                    del _redis_client[key]
            return None
        else:
            # 使用Redis
            data = _redis_client.get(key)
            if data:
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return None
            return None

    @staticmethod
    def set(key: str, value: Any, expire_time: int = DEFAULT_EXPIRE_TIME) -> None:
        """设置缓存数据"""
        if isinstance(_redis_client, dict):
            # 使用内存字典
            _redis_client[key] = ({'value': value, '_expire_time': expire_time}, time.time())
        else:
            # 使用Redis
            _redis_client.setex(key, expire_time, json.dumps(value))

    @staticmethod
    def delete(key: str) -> None:
        """删除缓存数据"""
        if isinstance(_redis_client, dict):
            if key in _redis_client:
                del _redis_client[key]
        else:
            _redis_client.delete(key)

    @staticmethod
    def clear(pattern: str = '*') -> None:
        """清除匹配模式的缓存"""
        if isinstance(_redis_client, dict):
            if pattern == '*':
                _redis_client.clear()
            else:
                # 简单的模式匹配实现
                keys_to_delete = [key for key in _redis_client if pattern in key]
                for key in keys_to_delete:
                    del _redis_client[key]
        else:
            for key in _redis_client.keys(pattern):
                _redis_client.delete(key)

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
def cache_dataframe_result(expire_time: int = DEFAULT_EXPIRE_TIME):
    """缓存pandas DataFrame结果的装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键，包含所有参数（包括分页参数）
            key = CacheService._generate_key(f"df_{func.__name__}", *args, **kwargs)
            
            # 尝试从缓存获取结果
            start_time = time.time()
            result_dict = CacheService.get(key)
            cache_check_time = time.time() - start_time
            
            if result_dict is not None:
                logger.info(f"缓存命中: {func.__name__}, 键: {key}, 耗时: {cache_check_time:.4f}秒")
                import pandas as pd
                # 缓存命中，将字典转回DataFrame或元组(如果是分页结果)
                try:
                    # 检查是否是分页结果（元组形式）
                    if isinstance(result_dict, dict) and 'is_paginated' in result_dict:
                        # 分页结果处理
                        df = pd.DataFrame(result_dict['data'])
                        if 'datetime' in df.columns:
                            df['datetime'] = pd.to_datetime(df['datetime'])
                        # 返回分页结果元组
                        logger.info(f"缓存数据解析完成: {func.__name__}, 分页数据行数: {len(df)}")
                        return df, result_dict['total_count']
                    else:
                        # 非分页结果处理
                        df = pd.DataFrame(result_dict)
                        if 'datetime' in df.columns:
                            df['datetime'] = pd.to_datetime(df['datetime'])
                        logger.info(f"缓存数据解析完成: {func.__name__}, 数据行数: {len(df)}")
                        return df
                except Exception as e:
                    logger.error(f"缓存数据解析失败: {func.__name__}, 错误: {e}")
                    # 如果解析失败，回退到重新计算
                    pass
            else:
                logger.info(f"缓存未命中: {func.__name__}, 键: {key}, 耗时: {cache_check_time:.4f}秒")
            
            # 缓存未命中，执行函数
            logger.info(f"执行原始函数: {func.__name__}, 参数: {args}, {kwargs}")
            start_execution = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_execution
            logger.info(f"原始函数执行完成: {func.__name__}, 耗时: {execution_time:.4f}秒")
            
            # 缓存结果，处理DataFrame或元组(分页结果)
            try:
                start_cache = time.time()
                
                # 检查是否是分页结果（元组形式）
                if isinstance(result, tuple) and len(result) == 2 and hasattr(result[0], 'to_dict'):
                    df, total_count = result
                    # 复制DataFrame以避免修改原始数据
                    df_copy = df.copy()
                    # 处理datetime列，转换为字符串
                    if 'datetime' in df_copy.columns:
                        df_copy['datetime'] = df_copy['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    # 转换为特殊格式的字典，表示这是分页结果
                    data_to_cache = {
                        'is_paginated': True,
                        'data': df_copy.to_dict(orient='records'),
                        'total_count': total_count
                    }
                    CacheService.set(key, data_to_cache, expire_time)
                    cache_time = time.time() - start_cache
                    logger.info(f"分页结果缓存完成: {func.__name__}, 键: {key}, 缓存数据大小: {len(data_to_cache['data'])}条, 总条数: {total_count}, 耗时: {cache_time:.4f}秒")
                elif result is not None and hasattr(result, 'to_dict'):
                    # 非分页结果处理
                    # 复制DataFrame以避免修改原始数据
                    df_copy = result.copy()
                    # 处理datetime列，转换为字符串
                    if 'datetime' in df_copy.columns:
                        df_copy['datetime'] = df_copy['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    # 转换为字典
                    data_to_cache = df_copy.to_dict(orient='records')
                    CacheService.set(key, data_to_cache, expire_time)
                    cache_time = time.time() - start_cache
                    logger.info(f"结果缓存完成: {func.__name__}, 键: {key}, 缓存数据大小: {len(data_to_cache)}条, 耗时: {cache_time:.4f}秒")
            except Exception as e:
                logger.error(f"缓存设置失败: {func.__name__}, 错误: {e}")
            
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