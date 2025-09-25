import ccxt
import psycopg2
from psycopg2.extras import execute_values
import ccxt

DB_CONFIG = {
    "dbname": "quant",
    "user": "cfs",
    "password": "Cc563479,.",
    "host": "127.0.0.1",
    "port": 5432
}

ENABLED_EXCHANGES = ["binance", "bybit", "coinbase", "upbit", "okx"]
# ENABLED_EXCHANGES = ["coinbase", "upbit", "okx"]

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def get_exchange(name):
    return {
        "binance": ccxt.binance,
        "bybit": ccxt.bybit,
        "coinbase": ccxt.coinbase,
        "upbit": ccxt.upbit,
        "okx": ccxt.okx,
    }[name]({"enableRateLimit": True})

def get_top_symbols(exchange, limit=50, quote_currencies=("USDT", "USDC", "USD")):
    markets = exchange.load_markets()
    symbols = [
        sym for sym, data in markets.items()
        if data.get("spot") and data["quote"] in quote_currencies
    ]
    try:
        tickers = exchange.fetch_tickers(symbols)
        sorted_syms = sorted(tickers.items(), key=lambda kv: kv[1].get("quoteVolume", 0), reverse=True)
        return [s for s, _ in sorted_syms[:limit]]
    except Exception:
        return symbols[:limit]

def upsert_codes(exchange, symbols):
    sql = """
    INSERT INTO market_codes (exchange, code, active, excode)
    VALUES %s
    ON CONFLICT (exchange, code) DO UPDATE SET 
        active = EXCLUDED.active,
        excode = EXCLUDED.excode
    """
    rows = [(exchange, s, True, f"{exchange}-{s}") for s in symbols]
    with get_conn() as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows)

if __name__ == "__main__":
    for name in ENABLED_EXCHANGES:
        ex = get_exchange(name)
        syms = get_top_symbols(ex, limit=50)
        upsert_codes(name, syms)
        print(f"[Init] {name} 已写入 {len(syms)} 个symbols")
