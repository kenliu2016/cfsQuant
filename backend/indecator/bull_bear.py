#!/usr/bin/env python3
"""
主程序：从 PostgreSQL 中读取 K 线数据与已持久化的 market_signals（取最近一条）进行牛/熊判定。
"""
import json
import os
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
import matplotlib.pyplot as plt
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


def fetch_klines(engine, table, exchange, symbol, since_hours=48):
    now = datetime.utcnow()
    since = now - timedelta(hours=since_hours)
    sql = text(f'''
        SELECT datetime, open, high, low, close, volume
        FROM {table}
        WHERE exchange = :exchange AND code = :code AND datetime >= :since
        ORDER BY datetime ASC
    ''')
    with engine.begin() as conn:
        df = pd.read_sql(sql, conn, params={'exchange': exchange, 'code': symbol, 'since': since})
    if df.empty:
        raise RuntimeError('No kline data returned. Check DB and table fields')
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
    return df


def fetch_latest_signals(engine, exchange, symbol):
    sql = text('''
        SELECT funding_rate, stablecoin_flow, datetime
        FROM market_signals
        WHERE exchange = :exchange AND symbol = :symbol
        ORDER BY datetime DESC
        LIMIT 1
    ''')
    with engine.begin() as conn:
        row = conn.execute(sql, {'exchange': exchange, 'symbol': symbol}).fetchone()
    if row:
        return {'funding_rate': row[0], 'stablecoin_flow': row[1], 'ts': row[2]}
    return {'funding_rate': None, 'stablecoin_flow': None, 'ts': None}


def compute_mas(df, short=50, long=200):
    df['ma_short'] = df['close'].rolling(window=short, min_periods=1).mean()
    df['ma_long'] = df['close'].rolling(window=long, min_periods=1).mean()
    return df


def vp_corr(df, window=24):
    w = min(len(df), window)
    r = df['close'].pct_change().fillna(0).tail(w)
    v = df['volume'].pct_change().fillna(0).tail(w)
    if r.std()==0 or v.std()==0:
        return 0.0
    return float(r.corr(v))


def price_structure_slopes(df):
    highs = df['high'].resample('1h').max().dropna()
    lows = df['low'].resample('1h').min().dropna()
    def slope(s):
        if len(s) < 3: return 0.0
        x = np.arange(len(s))
        return float(np.polyfit(x, s.values, 1)[0])
    return slope(highs[-24:]), slope(lows[-24:])


def score_and_decide(df, signals):
    score = 0
    reasons = []
    last_close = float(df['close'].iloc[-1])
    ma_s = float(df['ma_short'].iloc[-1])
    ma_l = float(df['ma_long'].iloc[-1])

    if last_close > ma_l:
        score += 2; reasons.append('price_above_ma_long')
    else:
        score -= 2; reasons.append('price_below_ma_long')

    if ma_s > ma_l:
        score += 1; reasons.append('ma_short_above_long')
    else:
        score -= 1; reasons.append('ma_short_below_long')

    hs, ls = price_structure_slopes(df)
    if hs>0 and ls>0:
        score += 1; reasons.append('higher_highs_higher_lows')
    elif hs<0 and ls<0:
        score -= 1; reasons.append('lower_highs_lower_lows')

    vpc = vp_corr(df)
    if vpc > 0.1:
        score += 1; reasons.append('volume_price_positive_corr')
    elif vpc < -0.1:
        score -= 1; reasons.append('volume_price_negative_corr')

    fr = signals.get('funding_rate')
    sc = signals.get('stablecoin_flow')
    if fr is not None:
        if float(fr) > 0:
            score += 1; reasons.append('positive_funding')
        else:
            score -= 1; reasons.append('negative_funding')
    if sc is not None:
        if float(sc) > 0:
            score += 1; reasons.append('stablecoin_inflow')
        else:
            score -= 1; reasons.append('stablecoin_outflow')

    phase = 'Neutral'
    if score >= 3:
        phase = 'Bull'
    elif score <= -3:
        phase = 'Bear'

    return {
        'score': int(score),
        'phase': phase,
        'reasons': reasons,
        'last_close': last_close,
        'ma_short': ma_s,
        'ma_long': ma_l,
        'vp_corr': float(vpc),
        'funding_rate': fr,
        'stablecoin_flow': sc,
        'signals_ts': signals.get('ts')
    }



def main():
    exchange = 'binance'
    symbol = 'binance-BTC/USDT'
    norm_symbol = 'BTCUSDT'
    kline_table = 'minute_realtime'
    lookback_hours = 48
    ma_short = 50
    ma_long = 200

    df = fetch_klines(engine, kline_table, exchange, symbol, lookback_hours)
    df = compute_mas(df, ma_short, ma_long)

    signals = fetch_latest_signals(engine, exchange, norm_symbol)
    result = score_and_decide(df, signals)
    print('Result:', result)

   

if __name__ == '__main__':
    main()