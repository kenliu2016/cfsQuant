import sys
import os

# 添加项目根目录到Python路径，以便能够导入app模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from common.logger import LoggerFactory

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("services.candles_cache")

from .cache_service import CacheService
from functools import wraps
import time
import json

# 默认过期时间（秒）
DEFAULT_EXPIRE_TIME = 60 * 5  # 5分钟

# 清除特定K线查询的缓存
def clear_candles_cache(code: str, interval: str = "1m", limit: int = None, 
                       start: str = None, end: str = None) -> bool:
    """
    清除特定K线查询的缓存
    
    Args:
        code: 市场代码，如"binance-BTC/USDT"
        interval: 时间间隔，如"1m", "15m", "1h", "1D"等
        limit: 查询的记录条数，如果为None则匹配所有limit值的查询
        start: 开始时间，如果为None则匹配所有start值的查询
        end: 结束时间，如果为None则匹配所有end值的查询
        
    Returns:
        bool: 操作是否成功
    """
    try:
        if start and end:
            # 清除基于时间范围的查询缓存（get_candles函数）
            # 生成函数调用的缓存键模式
            key_pattern = _generate_candles_key_pattern("get_candles", code, interval, start, end)
            logger.info(f"清除基于时间范围的K线缓存，模式: {key_pattern}")
            CacheService.clear(key_pattern)
        elif limit:
            # 清除基于limit的查询缓存（get_latest_candles函数）
            # 生成函数调用的缓存键模式
            key_pattern = _generate_candles_key_pattern("get_latest_candles", code, interval, limit=limit)
            logger.info(f"清除基于limit的K线缓存，模式: {key_pattern}")
            CacheService.clear(key_pattern)
        else:
            # 清除该代码的所有K线缓存
            logger.info(f"清除代码 {code} 的所有K线缓存")
            CacheService.clear(f"market:{code}:*")
        
        return True
    except Exception as e:
        logger.error(f"清除K线缓存失败: {str(e)}")
        return False

# 生成K线缓存键模式
def _generate_candles_key_pattern(func_name: str, code: str, interval: str, start: str = None, 
                                 end: str = None, limit: int = None) -> str:
    """
    生成K线缓存键的匹配模式
    注意：这不是精确的缓存键生成，而是用于模式匹配的简化版本
    """
    # 对于get_latest_candles函数
    if func_name == "get_latest_candles":
        # 函数签名: get_latest_candles(code, interval="1m", limit=2)
        # 缓存键包含这些参数
        if limit is not None:
            # 生成包含code、interval和limit的键模式
            return f"*df_{func_name}*{code}*interval={interval}*limit={limit}*"
        else:
            # 生成包含code和interval的键模式
            return f"*df_{func_name}*{code}*interval={interval}*"
    
    # 对于get_candles函数
    elif func_name == "get_candles":
        # 函数签名: get_candles(code, start, end, interval="1m", page=None, page_size=None)
        # 缓存键包含这些参数
        if start and end:
            # 生成包含code、start、end和interval的键模式
            # 注意：start和end在缓存键中会被转换为字符串，这里使用通配符匹配
            return f"*df_{func_name}*{code}*{start}*{end}*interval={interval}*"
        else:
            # 生成包含code和interval的键模式
            return f"*df_{func_name}*{code}*interval={interval}*"
    
    # 默认返回包含code的模式
    return f"*df_{func_name}*{code}*"

# 清除所有K线缓存
def clear_all_candles_cache() -> bool:
    """
    清除所有K线相关的缓存
    
    Returns:
        bool: 操作是否成功
    """
    try:
        logger.info("清除所有K线缓存")
        # 清除所有以df_get_candles和df_get_latest_candles开头的缓存键
        CacheService.clear("*df_get_candles*")
        CacheService.clear("*df_get_latest_candles*")
        # 清除所有market:前缀的缓存键
        CacheService.clear("market:*")
        return True
    except Exception as e:
        logger.error(f"清除所有K线缓存失败: {str(e)}")
        return False

# 刷新特定K线数据（清除缓存后强制重新加载）
def refresh_candles_data(code: str, interval: str = "1m", limit: int = None, 
                        start: str = None, end: str = None) -> bool:
    """
    刷新特定K线数据（清除缓存后强制重新加载）
    
    Args:
        code: 市场代码，如"binance-BTC/USDT"
        interval: 时间间隔，如"1m", "15m", "1h", "1D"等
        limit: 查询的记录条数
        start: 开始时间
        end: 结束时间
        
    Returns:
        bool: 操作是否成功
    """
    # 先清除缓存
    result = clear_candles_cache(code, interval, limit, start, end)
    
    if result:
        logger.info(f"成功刷新K线数据缓存: code={code}, interval={interval}")
    else:
        logger.error(f"刷新K线数据缓存失败: code={code}, interval={interval}")
        
    return result