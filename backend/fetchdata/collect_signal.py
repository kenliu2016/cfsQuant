
#!/usr/bin/env python3
"""
信号采集器：从 Binance 获取资金费率与稳定币流入代理信号，并持久化到 PostgreSQL 表 market_signals。
该脚本适合被周期性（cron）或容器调度器触发。
"""
import json
import requests
from datetime import datetime
from sqlalchemy import text
import sys
import os


# 添加项目根目录和backend目录到Python路径，以便能导入app.db
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
backend_dir = os.path.join(project_root, 'backend')
sys.path.append(project_root)
sys.path.append(backend_dir)

from app.db import get_engine

# === PostgreSQL 连接 ===
engine = get_engine()


def ensure_table(engine):
    sql = '''
    CREATE TABLE IF NOT EXISTS public.indecator_metrics (
        id SERIAL PRIMARY KEY,
        exchange VARCHAR NOT NULL,
        symbol VARCHAR NOT NULL,
        datetime TIMESTAMP NOT NULL DEFAULT now(),
        funding_rate NUMERIC,
        stablecoin_flow NUMERIC,
        created_at TIMESTAMP DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS indecator_metrics_idx ON public.indecator_metrics (exchange, symbol, datetime);
    '''
    with engine.begin() as conn:
        conn.execute(text(sql))


def fetch_latest_funding_rate(symbol='BTCUSDT'):
    # 取最新一条资金费率（永续合约 funding rate）
    url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1"
    r = requests.get(url, timeout=10)
    data = r.json()
    if isinstance(data, list) and data:
        return float(data[0].get('fundingRate', 0.0))
    return None


def fetch_stablecoin_flow_proxy():
    # 由于 Binance 没有直接稳定币整体流入API，此处用稳定币相关交易对 quoteVolume 的均值作为代理
    url = 'https://api.binance.com/api/v3/ticker/24hr'
    r = requests.get(url, timeout=10)
    tickers = r.json()
    stablecoins = ['USDT', 'USDC', 'FDUSD', 'BUSD']
    total_quote_vol = 0.0
    count = 0
    for t in tickers:
        sym = t.get('symbol','')
        # 仅统计以稳定币为计价货币（例如 XXXUSDT）
        if any(st in sym for st in stablecoins) and sym.endswith('USDT'):
            qv = float(t.get('quoteVolume', 0) or 0)
            if qv > 0:
                total_quote_vol += qv
                count += 1
    if count == 0:
        return None
    avg = total_quote_vol / count
    # 缩放为更易存储和比较的数值（可调整）
    return float((avg ** 0.5) / 1e3)


def persist_signal(engine, exchange, symbol, funding_rate, stablecoin_flow):
    sql = text('''
        INSERT INTO indecator_metrics (exchange, symbol, funding_rate, stablecoin_flow)
        VALUES (:exchange, :symbol, :funding_rate, :stablecoin_flow)
    ''')
    with engine.begin() as conn:
        conn.execute(sql, {
            'exchange': exchange,
            'symbol': symbol,
            'funding_rate': funding_rate,
            'stablecoin_flow': stablecoin_flow
        })


def main():
    ensure_table(engine)

    exchange = 'binance'
    symbol = 'BTCUSDT'

    print(f'[{datetime.utcnow().isoformat()}] Collecting signals for {exchange} {symbol} ...')
    fr = None
    sc = None
    try:
        fr = fetch_latest_funding_rate(symbol)
    except Exception as e:
        print('Error fetching funding rate:', e)
    try:
        sc = fetch_stablecoin_flow_proxy()
    except Exception as e:
        print('Error fetching stablecoin flow proxy:', e)

    print('Fetched -> funding_rate:', fr, 'stablecoin_flow:', sc)
    persist_signal(engine, exchange, symbol, fr, sc)
    print('[OK] Persisted signal to DB')

if __name__ == '__main__':
    main()