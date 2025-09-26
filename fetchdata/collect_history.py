import ccxt
import pandas as pd
import psycopg2
import time
import json
from decimal import Decimal
from datetime import datetime, timedelta, timezone

DB_CONFIG = {
    "dbname": "quant",
    "user": "your_cfs",
    "password": "Cc563479,.",
    "host": "127.0.0.1",
    "port": 5432
}

def json_default(obj):
    if isinstance(obj, (Decimal,float)):
        return float(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return str(obj)

EXCHANGE_CLASSES = {
    "binance": ccxt.binance,
    "bybit": ccxt.bybit,
    "coinbase": ccxt.coinbase,
    "upbit": ccxt.upbit,
    "okx": ccxt.okx
}

def get_exchange(name):
    return EXCHANGE_CLASSES[name]({"enableRateLimit": True})

def safe_call(func, *args, retries=5, delay=2, **kwargs):
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"[WARN] 调用失败 {func.__name__}: {e} (重试{i+1})", flush=True)
            time.sleep(delay*(i+1))
    return []

def upsert_ohlcv(exchange, symbol, df, timeframe, conn):
    if df.empty:
        return
    table_map = {"1m":"minute_realtime","1h":"hour_realtime","1d":"day_realtime"}
    table = table_map[timeframe]
    ts_col = "datetime"
    rows = []
    for _, row in df.iterrows():
        dt = row["timestamp"].to_pydatetime().replace(tzinfo=None) if timeframe!="1d" else row["timestamp"].date()
        row_dict = row.to_dict()
        row_dict.pop("timestamp", None)
        raw_json = json.dumps(row_dict, default=json_default)
        # 将exchange和symbol用连字符连接作为code字段值
        combined_code = f"{exchange}-{symbol}"
        rows.append((exchange, combined_code, dt,
                     float(row["open"]), float(row["high"]), float(row["low"]),
                     float(row["close"]), float(row["volume"]), raw_json))
    from psycopg2.extras import execute_values
    with conn.cursor() as cur:
        execute_values(cur,
            f"INSERT INTO {table} (exchange, code, {ts_col}, open, high, low, close, volume, raw) "
            f"VALUES %s ON CONFLICT (exchange, code, {ts_col}) DO UPDATE "
            f"SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close, "
            f"volume=EXCLUDED.volume, raw=EXCLUDED.raw, updated_at=now()",
            rows
        )
    conn.commit()
    print(f"[INFO] {exchange} {symbol} {timeframe} 写入 {len(df)} 条", flush=True)

def fetch_ohlcv_last_3y(exchange, symbol, timeframe, conn, limit=1000):
    # 使用 timezone.utc 替代 datetime.UTC 以兼容较旧的 Python 版本
    since = int((datetime.now(timezone.utc) - timedelta(days=365*3)).timestamp() * 1000)
    ms_in_tf = {"1m": 60*1000, "1h": 3600*1000, "1d": 86400*1000}[timeframe]

    while True:
        ohlcv = safe_call(exchange.fetch_ohlcv, symbol, timeframe, since, limit)
        if not ohlcv:
            break
        df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            upsert_ohlcv(exchange.id, symbol, df, timeframe, conn)
            since = int(df["timestamp"].iloc[-1].timestamp()*1000 + ms_in_tf)
        if len(ohlcv) < limit:
            break
        time.sleep(exchange.rateLimit/1000 + 0.2)

if __name__=="__main__":
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT exchange, code FROM market_codes WHERE active=TRUE")
            codes = cur.fetchall()
        for exchange_name, symbol in codes:
            try:
                ex = get_exchange(exchange_name)
                for tf in ["1m","1h","1d"]:
                    fetch_ohlcv_last_3y(ex, symbol, tf, conn)
            except (ccxt.NetworkError, ccxt.ExchangeError) as e:
                print(f"[WARN] {exchange_name} {symbol} 访问失败，跳过: {e}", flush=True)