import ccxt
from psycopg2.extras import execute_values
import sys
import os
import time
import random
from functools import wraps

# 添加common.db模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from common.db import get_connection
from common.logger import LoggerFactory

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("fetchdata.init_symbols")

# 重试机制配置
MAX_RETRIES = 3
BASE_DELAY = 1  # 基础延迟秒数
MAX_DELAY = 60  # 最大延迟秒数

# 速率限制配置
RATE_LIMIT_DELAY = 0.1  # 每次API调用之间的基础延迟

# 重试装饰器
def retry_with_backoff(max_retries=MAX_RETRIES, base_delay=BASE_DELAY, max_delay=MAX_DELAY):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"函数 {func.__name__} 重试 {max_retries} 次后仍然失败: {e}")
                        raise
                    
                    # 指数退避算法
                    delay = min(base_delay * (2 ** (retries - 1)) + random.uniform(0, 1), max_delay)
                    logger.warning(f"函数 {func.__name__} 第 {retries} 次重试，等待 {delay:.2f} 秒后重试。错误: {e}")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

# 速率限制装饰器
def rate_limit(delay=RATE_LIMIT_DELAY):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            time.sleep(delay)
            return func(*args, **kwargs)
        return wrapper
    return decorator

ENABLED_EXCHANGES = ["binance"]
# ENABLED_EXCHANGES = ["binance", "bybit", "coinbase", "upbit", "okx"]

def get_exchange(name):
    return {
        "binance": ccxt.binance,
        "bybit": ccxt.bybit,
        "coinbase": ccxt.coinbase,
        "upbit": ccxt.upbit,
        "okx": ccxt.okx,
    }[name]({"enableRateLimit": True})

@retry_with_backoff(max_retries=3, base_delay=2, max_delay=30)
@rate_limit(delay=0.2)
def get_top_symbols(exchange, limit=None):
    markets = exchange.load_markets()
    
    # 定义需要排除的稳定币列表
    stablecoins = {"USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "USDN", "FRAX", "USDD", "GUSD"}
    
    symbols = [
        sym for sym, data in markets.items()
        if (data.get("spot") and 
            # 排除稳定币对：确保基础货币不是稳定币
            data["base"] not in stablecoins)
    ]
    
    # 分批获取ticker数据，避免API限制
    batch_size = 100
    all_tickers = {}
    
    for i in range(0, len(symbols), batch_size):
        batch_symbols = symbols[i:i + batch_size]
        try:
            batch_tickers = exchange.fetch_tickers(batch_symbols)
            all_tickers.update(batch_tickers)
            logger.info(f"批次 {i//batch_size + 1}/{(len(symbols)-1)//batch_size + 1} 成功获取 {len(batch_tickers)} 个ticker数据")
            
            # 批次间延迟，避免触发API限速
            time.sleep(1)
            
        except Exception as e:
            logger.warning(f"批次 {i//batch_size + 1} 获取ticker数据失败: {e}")
            continue
    
    # 如果获取ticker数据失败，返回原始symbols
    if not all_tickers:
        logger.warning("无法获取ticker数据，返回原始symbols列表")
        return symbols if limit is None else symbols[:limit]
    
    sorted_syms = sorted(all_tickers.items(), key=lambda kv: kv[1].get("quoteVolume", 0), reverse=True)
    
    # 如果没有设置limit，返回所有symbols
    if limit is None:
        return [s for s, _ in sorted_syms]
    else:
        return [s for s, _ in sorted_syms[:limit]]

@retry_with_backoff(max_retries=3, base_delay=1, max_delay=10)
def upsert_codes(exchange, symbols):
    sql = """
    INSERT INTO market_codes (exchange, code, active, excode, baseCurrency, quoteCurrency)
    VALUES %s
    ON CONFLICT (exchange, code) DO UPDATE SET 
        active = EXCLUDED.active,
        excode = EXCLUDED.excode,
        baseCurrency = EXCLUDED.baseCurrency,
        quoteCurrency = EXCLUDED.quoteCurrency,
        updated_at = timezone('utc', now())
    """
    rows = []
    for s in symbols:
        # 根据"/"拆解symbol为baseCurrency和quoteCurrency
        if '/' in s:
            base_currency, quote_currency = s.split('/', 1)
        else:
            # 如果没有"/"，则整个symbol作为baseCurrency，quoteCurrency设为空
            base_currency = s
            quote_currency = ''
        
        rows.append((exchange, s, False, f"{exchange}-{s}", base_currency, quote_currency))
    
    with get_connection() as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows)

if __name__ == "__main__":
    for name in ENABLED_EXCHANGES:
        try:
            logger.info(f"开始处理交易所: {name}")
            ex = get_exchange(name)
            syms = get_top_symbols(ex)  # 不设限制，获取所有symbols
            upsert_codes(name, syms)
            logger.info(f"{name} 已写入 {len(syms)} 个symbols")
        except Exception as e:
            logger.error(f"处理交易所 {name} 时出错: {e}")
            continue
