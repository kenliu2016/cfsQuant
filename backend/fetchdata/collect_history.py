import ccxt
import psycopg2
import pandas as pd
import time
import ccxt
from datetime import datetime, timedelta, timezone

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "quant",
    "user": "cfs",
    "password": "Cc563479,.",
}

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
    if table in ["minute_realtime", "hour_realtime"]:
        month_start = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        partition_name = f"{table}_{month_start.strftime('%Y_%m')}"
        sql = f"""
        CREATE TABLE IF NOT EXISTS {partition_name}
        PARTITION OF {table}
        FOR VALUES FROM ('{month_start.strftime('%Y-%m-%d')}') 
                     TO ('{next_month.strftime('%Y-%m-%d')}')
        """
    elif table == "day_realtime":
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

    table_map = {"1m": "minute_realtime", "1h": "hour_realtime", "1d": "day_realtime"}
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
    print(f"[INFO] {exchange} {symbol} {timeframe} 写入 {len(df)} 条", flush=True)

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
            print(f"[WARN] {exchange_name} {symbol} {timeframe} fetch_ohlcv 出错: {e}, 等待 5 秒重试")
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
    start_time = end_time - timedelta(days=365*3)  # 最近三年

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT exchange, code FROM market_codes WHERE active=true")
            codes = cur.fetchall()
        print(f"[DEBUG] 查询到 {len(codes)} 个交易对")

        for exchange_name, symbol in codes:
            try:
                ex = get_exchange(exchange_name)
            except Exception as e:
                print(f"[ERROR] 无法创建交易所 {exchange_name}: {e}")
                continue

            for tf in ["1m","1h","1d"]:
                print(f"[START] {exchange_name} {symbol} {tf} 从 {start_time} 到 {end_time}")
                fetch_ohlcv_paginated(ex, exchange_name, symbol, tf, start_time, end_time, conn)
                print(f"[DONE] {exchange_name} {symbol} {tf} 三年历史补齐完成")