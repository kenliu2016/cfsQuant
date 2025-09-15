import argparse
import time
import datetime
from binance.client import Client
from sqlalchemy import text
from app.db import get_engine
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import logging
import os

# ----------------- 日志配置 -----------------
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "binance_ingest.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# -------------------------------------------

# Binance API 初始化（拉取公开数据可不填 key/secret）
api_key = ""
api_secret = ""
client = Client(api_key, api_secret)


def save_batch_to_db(batch, symbol, table):
    """将一批K线数据批量保存到数据库"""
    if not batch:
        return

    engine = get_engine()
    records = [{
        "datetime": datetime.datetime.fromtimestamp(row[0] / 1000),
        "code": symbol,
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "volume": float(row[5])
    } for row in batch]

    sql = text(f"""
        INSERT INTO {table} (datetime, code, open, high, low, close, volume)
        VALUES (:datetime, :code, :open, :high, :low, :close, :volume)
        ON CONFLICT (datetime, code) DO NOTHING
    """)
    with engine.begin() as conn:
        conn.execute(sql, records)


def fetch_and_save(symbol, interval, start, end, table, max_retries=3):
    """循环分页拉取 Binance 历史K线，并批量保存"""
    limit = 1000
    current = start
    total_saved = 0
    retries = 0

    while True:
        try:
            data = client.get_klines(
                symbol=symbol,
                interval=interval,
                startTime=current,
                endTime=end,
                limit=limit
            )
        except Exception as e:
            retries += 1
            if retries > max_retries:
                msg = f"{symbol}: 获取数据失败，已重试 {max_retries} 次: {e}"
                logger.error(msg)
                raise RuntimeError(msg)
            logger.warning(f"{symbol}: 获取数据失败，重试中 ({retries}/{max_retries}) ... {e}")
            time.sleep(1)
            continue

        if not data:
            break

        save_batch_to_db(data, symbol, table)
        total_saved += len(data)
        logger.info(f"{symbol}: 已保存累计 {total_saved} 条记录")

        last_open_time = data[-1][0]
        current = last_open_time + 1  # 避免重复拉取
        time.sleep(0.2)

        if len(data) < limit:
            break

    return f"✅ {symbol}: 拉取完成，累计保存 {total_saved} 条记录"


def get_last_timestamp(symbol, table):
    """查数据库里已有的最新时间"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT MAX(datetime) FROM {table} WHERE code=:code"),
            {"code": symbol}
        ).scalar()
    return result


def run_task(symbol, interval, start_ts, end_ts, force):
    """执行单币种拉取任务"""
    table = "minute_realtime" if interval.endswith("m") else "day_realtime"
    last_time = get_last_timestamp(symbol, table)

    if not force and last_time:
        # 自动从最新记录之后继续拉取
        next_ts = int(last_time.timestamp() * 1000)
        if not start_ts or next_ts > start_ts:
            start_ts = next_ts + (60_000 if interval.endswith("m") else 24*60*60*1000)
            logger.info(f"{symbol}: 从数据库已有记录之后继续拉取: {datetime.datetime.fromtimestamp(start_ts/1000)}")

    logger.info(f"{symbol}: 开始拉取 {interval} K线")
    return fetch_and_save(symbol, interval, start_ts, end_ts, table)


def main():
    parser = argparse.ArgumentParser(description="Binance 数据拉取器（支持分钟线/日线，自动选择表）")
    parser.add_argument("--symbols", type=str, default="BTCUSDT", help="交易对列表，用逗号分隔")
    parser.add_argument("--interval", type=str, default="1m", help="K线周期，如 1m/5m/1h/1d")
    parser.add_argument("--start", type=str, default=None, help="起始日期，如 2023-01-01")
    parser.add_argument("--end", type=str, default=None, help="结束日期，如 2023-02-01")
    parser.add_argument("--force", action="store_true", help="忽略已有数据，强制从 start 开始拉取")
    parser.add_argument("--workers", type=int, default=3, help="并发线程数")
    args = parser.parse_args()

    start_ts = int(datetime.datetime.fromisoformat(args.start).timestamp() * 1000) if args.start else None
    end_ts = int(datetime.datetime.fromisoformat(args.end).timestamp() * 1000) if args.end else None
    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_task, sym, args.interval, start_ts, end_ts, args.force): sym for sym in symbols}
        for future in tqdm(as_completed(futures), total=len(futures), desc="任务进度"):
            sym = futures[future]
            try:
                msg = future.result()
                results.append(msg)
            except Exception as e:
                err = f"❌ {sym} 拉取失败: {e}"
                logger.error(err)
                results.append(err)

    print("\n--- 执行结果 ---")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
