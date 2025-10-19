import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta, timezone
import sys
import os

# 添加项目根目录到Python路径，以便能够导入common模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.logger import LoggerFactory
from common.db import get_connection

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("fetchdata.history")

# ================== 工具 ==================
def get_exchange(name):
    """根据交易所名字返回 ccxt 实例"""
    exchanges = {
        "binance": ccxt.binance,
        "bybit": ccxt.bybit,
        "okx": ccxt.okx,
        "coinbase": ccxt.coinbase,
        "upbit": ccxt.upbit,
    }
    if name not in exchanges:
        raise ValueError(f"不支持的交易所: {name}")
    ex = exchanges[name]({"enableRateLimit": True})
    return ex

# ================== 分区工具 ==================
def ensure_partition(conn, table, target_date):
    """在写入前确保分区存在"""
    if table in ["market_minute_klines", "market_hour_klines"]:
        month_start = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        partition_name = f"{table}_{month_start.strftime('%Y_%m')}"
        sql = f"""
        CREATE TABLE IF NOT EXISTS {partition_name}
        PARTITION OF {table}
        FOR VALUES FROM ('{month_start.strftime('%Y-%m-%d')}') 
                     TO ('{next_month.strftime('%Y-%m-%d')}')
        """
    elif table == "market_day_klines":
        year_start = target_date.replace(month=1, day=1)
        next_year = year_start.replace(year=year_start.year + 1)
        partition_name = f"{table}_{year_start.year}"
        sql = f"""
        CREATE TABLE IF NOT EXISTS {partition_name}
        PARTITION OF {table}
        FOR VALUES FROM ('{year_start.strftime('%Y-%m-%d')}') 
                     TO ('{next_year.strftime('%Y-%m-%d')}')
        """
    else:
        return

    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    # print(f"[INFO] 确保分区存在: {partition_name}", flush=True)

# ================== 数据写入 ==================
def upsert_ohlcv(exchange, symbol, df, timeframe, conn):
    """插入或更新 OHLCV 数据"""
    if df.empty:
        return

    table_map = {"1m": "market_minute_klines", "1h": "market_hour_klines", "1d": "market_day_klines"}
    table = table_map[timeframe]
    # 生成 code 值，格式为 exchange-code
    code = f"{exchange}-{symbol}"

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            ensure_partition(conn, table, row["timestamp"].to_pydatetime())
            cur.execute(f"""
                INSERT INTO {table} 
                (exchange, code, datetime, open, high, low, close, volume, raw)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (exchange, code, datetime) DO UPDATE
                SET open=EXCLUDED.open,
                    high=EXCLUDED.high,
                    low=EXCLUDED.low,
                    close=EXCLUDED.close,
                    volume=EXCLUDED.volume,
                    raw=EXCLUDED.raw,
                    updated_at=now()
            """, (
                exchange,
                code,
                row["timestamp"].to_pydatetime() if timeframe != "1d" else row["timestamp"].date(),
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row["volume"]),
                row.to_json(),
            ))
    conn.commit()
    logger.info(f"{exchange} {symbol} {timeframe} 历史写入 {len(df)} 条")

# ================== 分页抓取 ==================
def fetch_ohlcv_paginated(exchange, exchange_name, symbol, timeframe, since, until, conn):
    """分页抓取历史 OHLCV，并边拉边写数据库"""
    limit = 1000
    ms_per_unit = {
        "1m": 60 * 1000,
        "1h": 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000
    }[timeframe]

    now_ms = int(until.timestamp() * 1000)
    since_ms = int(since.timestamp() * 1000)

    while since_ms < now_ms:
        try:
            data = exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=limit)
        except Exception as e:
            logger.warning(f"{exchange_name} {symbol} {timeframe} fetch_ohlcv 出错: {e}, 等待 5 秒重试")
            time.sleep(5)
            continue

        if not data:
            break

        df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

        upsert_ohlcv(exchange_name, symbol, df, timeframe, conn)

        since_ms = int(df["timestamp"].iloc[-1].timestamp() * 1000) + ms_per_unit
        time.sleep(exchange.rateLimit / 1000)

# ================== 主入口 ==================
if __name__ == "__main__":
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=10)  # 最近三年

    # 获取活跃交易对
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT exchange, code FROM market_codes WHERE active=true")
        codes = cur.fetchall()
    logger.info(f"查询到 {len(codes)} 个交易对")

    # 创建交易所实例
    exchanges = {}
    for exchange_name, symbol in codes:
        if exchange_name not in exchanges:
            try:
                ex = get_exchange(exchange_name)
                exchanges[exchange_name] = ex
                logger.info(f"创建交易所实例: {exchange_name}")
            except Exception as e:
                logger.error(f"无法创建交易所 {exchange_name}: {e}")
                continue

    # 主循环
    for exchange_name, symbol in codes:
        if exchange_name not in exchanges:
            continue
        ex = exchanges[exchange_name]
        
        for tf in ["1m","1h","1d"]:
            logger.info(f"开始采集 {exchange_name} {symbol} {tf}")
            try:
                with get_connection() as conn:
                    fetch_ohlcv_paginated(ex, exchange_name, symbol, tf, start_time, end_time, conn)
                logger.info(f"{exchange_name} {symbol} {tf} 采集完成")
            except Exception as e:
                logger.error(f"{exchange_name} {symbol} {tf} 采集失败: {e}")

    logger.info("历史数据采集完成")