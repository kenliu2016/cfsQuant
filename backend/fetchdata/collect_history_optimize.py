import ccxt
import pandas as pd
import psycopg2
import time
from datetime import datetime, timedelta

# =========================
# 数据库写入函数
# =========================
def upsert_ohlcv(exchange, symbol, df, timeframe, conn):
    if df.empty:
        return
    table = f"ohlcv_{timeframe}"
    cur = conn.cursor()
    for _, row in df.iterrows():
        cur.execute(f"""
            INSERT INTO {table} (exchange, code, timestamp, open, high, low, close, volume)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (exchange, code, timestamp) DO NOTHING
        """, (
            exchange,
            symbol,
            row["timestamp"].to_pydatetime(),
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            float(row["volume"])
        ))
    conn.commit()
    cur.close()
    print(f"[DEBUG] {exchange} {symbol} {timeframe} 写入 {len(df)} 条")

# =========================
# 分页抓取函数
# =========================
def fetch_ohlcv_paginated(exchange, exchange_name, symbol, timeframe, since, until, conn):
    if exchange_name in ["coinbase", "upbit"]:
        limit = 200 if exchange_name == "upbit" else 300
    else:
        limit = 1000

    ms_per_unit = {
        "1m": 60 * 1000,
        "1h": 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000
    }[timeframe]

    since_ms = int(since.timestamp() * 1000)
    until_ms = int(until.timestamp() * 1000)

    while since_ms < until_ms:
        try:
            data = exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=limit)
        except Exception as e:
            print(f"[WARN] {exchange_name} {symbol} {timeframe} 出错: {e}, 5秒后重试")
            time.sleep(5)
            continue

        if not data:
            break

        df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

        upsert_ohlcv(exchange_name, symbol, df, timeframe, conn)

        # 翻页逻辑
        if exchange_name in ["binance", "okx", "coinbase"]:
            since_ms = int(df["timestamp"].iloc[-1].timestamp() * 1000) + ms_per_unit
        elif exchange_name == "bybit":
            last_ts = int(df["timestamp"].iloc[-1].timestamp() * 1000)
            since_ms = last_ts + ms_per_unit
        elif exchange_name == "upbit":
            last_ts = int(df["timestamp"].iloc[-1].timestamp() * 1000)
            since_ms = last_ts + ms_per_unit
            if len(df) < limit:
                break

        time.sleep(exchange.rateLimit / 1000)

# =========================
# 主流程
# =========================
def main():
    # 连接数据库
    conn = psycopg2.connect(
        dbname="quqnt",
        user="cfs",
        password="Aa520@cfs",
        host="localhost",
        port=5432
    )

    # 支持的交易所
    exchanges = {
        "binance": ccxt.binance({"enableRateLimit": True}),
        "okx": ccxt.okx({"enableRateLimit": True}),
        "bybit": ccxt.bybit({"enableRateLimit": True}),
        "coinbase": ccxt.coinbase({"enableRateLimit": True}),
        "upbit": ccxt.upbit({"enableRateLimit": True}),
    }

    # 时间范围：最近三年
    until = datetime.utcnow()
    since = until - timedelta(days=365*3)

    # 示例：每个交易所选 5 个 symbol（实际从数据库取 top50）
    sample_symbols = {
        "binance": ["BTC/USDT", "ETH/USDT"],
        "okx": ["BTC/USDT", "ETH/USDT"],
        "bybit": ["BTC/USDT", "ETH/USDT"],
        "coinbase": ["BTC/USDT", "ETH/USDT"],
        "upbit": ["BTC/USDT", "ETH/USDT"],
    }

    for ex_name, ex in exchanges.items():
        for symbol in sample_symbols[ex_name]:
            for tf in ["1m", "1h", "1d"]:
                print(f"[START] {ex_name} {symbol} {tf}")
                fetch_ohlcv_paginated(ex, ex_name, symbol, tf, since, until, conn)

    conn.close()

if __name__ == "__main__":
    main()
