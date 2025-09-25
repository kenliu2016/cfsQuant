import ccxt
import psycopg2
import pandas as pd
import time
import ccxt
from datetime import datetime, timedelta

# ================== 数据库配置 ==================
DB_CONFIG = {
    "dbname": "quant",
    "user": "cfs",
    "password": "Cc563479,.",
    "host": "127.0.0.1",
    "port": 5432
}

# ================== 工具函数 ==================
def get_exchange(name):
    exchanges = {
        "binance": ccxt.binance,
        "bybit": ccxt.bybit,
        "okx": ccxt.okx,
        "coinbase": ccxt.coinbase,
        "upbit": ccxt.upbit,
    }
    if name not in exchanges:
        raise ValueError(f"不支持的交易所: {name}")
    return exchanges[name]({"enableRateLimit": True})

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
    print(f"[INFO] {exchange} {symbol} {timeframe} 实时写入 {len(df)} 条", flush=True)

def fetch_latest_ohlcv(exchange, symbol, timeframe="1m", limit=100):
    """获取最新 N 根 K 线"""
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    except Exception as e:
        print(f"[WARN] fetch_latest_ohlcv {exchange.id} {symbol} {timeframe} 出错: {e}")
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

# ================== 主入口 ==================
if __name__ == "__main__":
    poll_interval = 60  # 每 60 秒轮询一次
    limit = 100         # 每次取最近 100 根 K 线

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT exchange, code FROM market_codes WHERE active=true")
            codes = cur.fetchall()
        print(f"[DEBUG] 查询到 {len(codes)} 个 active=true 交易对")

        while True:
            for exchange_name, symbol in codes:
                try:
                    ex = get_exchange(exchange_name)
                except Exception as e:
                    print(f"[ERROR] 无法初始化交易所 {exchange_name}: {e}")
                    continue

                for tf in ["1m","1h","1d"]:
                    df = fetch_latest_ohlcv(ex, symbol, tf, limit=limit)
                    if df.empty:
                        continue
                    upsert_ohlcv(exchange_name, symbol, df, tf, conn)

            print(f"[LOOP] 本轮实时采集完成 {datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
            time.sleep(poll_interval)
