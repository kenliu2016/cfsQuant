import ccxt
import psycopg2
from psycopg2.extras import execute_values
import sys
import os

from sqlalchemy import false

# 添加common.db模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from common.db import get_connection

ENABLED_EXCHANGES = ["binance", "bybit", "coinbase", "upbit", "okx"]
# ENABLED_EXCHANGES = ["coinbase", "upbit", "okx"]

def get_exchange(name):
    return {
        "binance": ccxt.binance,
        "bybit": ccxt.bybit,
        "coinbase": ccxt.coinbase,
        "upbit": ccxt.upbit,
        "okx": ccxt.okx,
    }[name]({"enableRateLimit": True})

def get_top_symbols(exchange, limit=50):
    markets = exchange.load_markets()
    
    # 定义需要排除的稳定币列表
    stablecoins = {"USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "USDN", "FRAX", "USDD", "GUSD"}
    
    symbols = [
        sym for sym, data in markets.items()
        if (data.get("spot") and 
            # 排除稳定币对：确保基础货币不是稳定币
            data["base"] not in stablecoins)
    ]
    try:
        tickers = exchange.fetch_tickers(symbols)
        sorted_syms = sorted(tickers.items(), key=lambda kv: kv[1].get("quoteVolume", 0), reverse=True)
        return [s for s, _ in sorted_syms[:limit]]
    except Exception:
        return symbols[:limit]

def upsert_codes(exchange, symbols):
    sql = """
    INSERT INTO market_codes (tenant_id, exchange, code, active, excode)
    VALUES %s
    ON CONFLICT (tenant_id, exchange, code) DO UPDATE SET 
        active = EXCLUDED.active,
        excode = EXCLUDED.excode
    """
    # 使用标准的tenant_id为'public'
    rows = [('public', exchange, s, False, f"{exchange}-{s}") for s in symbols]
    with get_connection() as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows)

if __name__ == "__main__":
    for name in ENABLED_EXCHANGES:
        try:
            print(f"开始处理交易所: {name}")
            ex = get_exchange(name)
            syms = get_top_symbols(ex, limit=50)
            upsert_codes(name, syms)
            print(f"[Init] {name} 已写入 {len(syms)} 个symbols")
        except Exception as e:
            print(f"处理交易所 {name} 时出错: {e}")
            continue
