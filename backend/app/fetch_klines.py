import asyncio
import aiohttp
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import argparse
import time
import json  # 添加json模块来正确处理JSON格式化

# ---------------- 配置 ----------------
PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'quant',
    'user': 'cfs',
    'password': 'Aa520@cfs'
}

BINANCE_US_API = "https://api.binance.us/api/v3/klines"
OKX_API = "https://www.okx.com/api/v5/market/candles"

MAX_RETRIES = 3
SLEEP_BASE = 2

INTERVAL_MAP = {'1m': '1m', '1h': '1h', '1d': '1d'}
TABLE_MAP = {'1m': 'minute_realtime_1', '1h': 'hour_realtime_1', '1d': 'day_realtime_1'}

# ---------------- 限速信号量 ----------------
BINANCE_SEMAPHORE = asyncio.Semaphore(5)  # 并发数控制
OKX_SEMAPHORE = asyncio.Semaphore(5)

# ---------------- PostgreSQL 工具 ----------------
def insert_klines_pg(conn, table, exchange, symbol, interval, klines):
    if not klines:
        return
    values = []
    for k in klines:
        try:
            if exchange == 'binance':
                ts = int(k[0]) / 1000
                o, h, l, c, v = map(float, k[1:6])
            else:  # okx
                ts = int(k[0]) / 1000
                o, h, l, c, v = map(float, k[1:6])
            dt = datetime.fromtimestamp(ts)
            if interval == '1d':
                dt = dt.date()
            
            # 使用json.dumps()代替str()来正确格式化JSON数据
            json_data = json.dumps(k)
            values.append((exchange, symbol, dt, o, h, l, c, v, json_data))
        except Exception as e:
            print(f"Error processing kline data for {symbol}: {e}")
            print(f"Problematic data: {k}")
            # 继续处理其他数据，而不是完全失败

    if not values:
        print(f"No valid data to insert for {symbol}")
        return

    try:
        with conn.cursor() as cur:
            execute_values(cur, f"""
                INSERT INTO {table} (exchange, code, datetime, open, high, low, close, volume, raw)
                VALUES %s
                ON CONFLICT (exchange, code, datetime) DO UPDATE
                SET open=EXCLUDED.open,
                    high=EXCLUDED.high,
                    low=EXCLUDED.low,
                    close=EXCLUDED.close,
                    volume=EXCLUDED.volume,
                    raw=EXCLUDED.raw
            """, values)
            conn.commit()
    except Exception as e:
        print(f"Database insertion error: {e}")
        conn.rollback()

# ---------------- 异步抓取 ----------------
async def fetch_binance(session, symbol, interval, limit=200):
    url = BINANCE_US_API
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    async with BINANCE_SEMAPHORE:  # 限速
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.get(url, params=params, timeout=5) as resp:
                    resp.raise_for_status()
                    await asyncio.sleep(0.1)  # 保持每秒约 10 次请求
                    return await resp.json()
            except Exception as e:
                print(f"[Binance.US] {symbol} attempt {attempt} failed: {e}")
                await asyncio.sleep(SLEEP_BASE * attempt)
    return []

async def fetch_okx(session, symbol, interval, limit=200):
    url = OKX_API
    interval_okx = interval.upper() if interval != '1m' else '1m'
    params = {'instId': symbol, 'bar': interval_okx, 'limit': str(limit)}
    async with OKX_SEMAPHORE:  # 限速
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.get(url, params=params, timeout=5) as resp:
                    resp.raise_for_status()
                    await asyncio.sleep(0.05)  # 保持每秒约 20 次请求
                    data = await resp.json()
                    if 'data' in data:
                        return data['data']
                    return []
            except Exception as e:
                print(f"[OKX] {symbol} attempt {attempt} failed: {e}")
                await asyncio.sleep(SLEEP_BASE * attempt)
    return []

async def fetch_all_symbols(symbols, interval, conn):
    table = TABLE_MAP.get(interval)
    if not table:
        raise ValueError(f"Invalid interval: {interval}")

    async with aiohttp.ClientSession() as session:
        tasks = []
        for symbol, exchange in symbols:
            if exchange.lower() == 'binance':
                tasks.append(fetch_binance(session, symbol, INTERVAL_MAP[interval]))
            elif exchange.lower() == 'okx':
                tasks.append(fetch_okx(session, symbol, INTERVAL_MAP[interval]))
        results = await asyncio.gather(*tasks)

    for (symbol, exchange), klines in zip(symbols, results):
        if klines:
            insert_klines_pg(conn, table, exchange.lower(), symbol, interval, klines)
            print(f"[{exchange}] Inserted {len(klines)} {interval} klines for {symbol}")

# ---------------- 主函数 ----------------
def main(interval='1m', test_only=False):
    start_time = datetime.now()
    conn = psycopg2.connect(**PG_CONFIG)
    try:

        with conn.cursor() as cur:
            cur.execute("SELECT code, exchange FROM market_codes WHERE active = true")
            symbols = cur.fetchall()

        asyncio.run(fetch_all_symbols(symbols, interval, conn))
        log_job(conn, 'fetch_binance_okx_klines_async', 'success', f'Fetched all {interval} klines', start_time)

    except Exception as e:
        print(f"Main function error: {e}")
        # 在事务外部创建新连接来记录错误，避免事务问题
        try:
            error_conn = psycopg2.connect(**PG_CONFIG)
            log_job(error_conn, 'fetch_binance_okx_klines_async', 'error', str(e), start_time)
            error_conn.close()
        except Exception as log_error:
            print(f"Failed to log error: {log_error}")
        raise
    finally:
        conn.close()

# ---------------- 记录作业函数 ----------------
def log_job(conn, job_name, status, message, start_time):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cron_log (job_name, status, message, started_at, ended_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (job_name, status, message, start_time))
            conn.commit()
    except Exception as e:
        print(f"Log job error: {e}")
        # 记录日志失败不应导致整个程序崩溃
        try:
            conn.rollback()
        except:
            pass

# ---------------- 命令行 ----------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', default='1m', choices=['1m','1h','1d'], help='Interval to fetch')
    parser.add_argument('--test', action='store_true', help='Run only test function')
    args = parser.parse_args()
    main(args.interval, args.test)