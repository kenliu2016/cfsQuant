#!/usr/bin/env python3
"""
牛熊判定指标计算器

功能：从 PostgreSQL 中读取 K 线数据与已持久化的市场信号（取最近一条）进行牛/熊判定。
结合技术指标（移动平均线、价格结构斜率、量价相关性）和基本面信号（资金费率、稳定币流入）进行综合评分。
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

from common.db import get_engine
from common.logger import LoggerFactory

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("indecator.bull_bear")

# === PostgreSQL 连接 ===
engine = get_engine()


def fetch_klines(engine, table, exchange, symbol, since_hours=48):
    """
    从数据库获取指定时间范围内的K线数据
    
    参数:
        engine: 数据库引擎
        table: K线数据表名
        exchange: 交易所名称
        symbol: 交易对符号
        since_hours: 回溯小时数，默认48小时
    
    返回:
        DataFrame: 包含datetime, open, high, low, close, volume的K线数据
    """
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
    """
    获取最新的市场信号数据（资金费率和稳定币流入）
    
    参数:
        engine: 数据库引擎
        exchange: 交易所名称
        symbol: 交易对符号
    
    返回:
        dict: 包含资金费率、稳定币流入和时间戳的字典
    """
    sql = text('''
        SELECT funding_rate, stablecoin_flow, datetime
        FROM indecator_metrics
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
    """
    计算移动平均线（MA）指标
    
    参数:
        df: 包含价格数据的DataFrame
        short: 短期移动平均窗口，默认50
        long: 长期移动平均窗口，默认200
    
    返回:
        DataFrame: 添加了ma_short和ma_long列的DataFrame
    """
    df['ma_short'] = df['close'].rolling(window=short, min_periods=1).mean()
    df['ma_long'] = df['close'].rolling(window=long, min_periods=1).mean()
    return df


def vp_corr(df, window=24):
    """
    计算量价相关性指标
    
    参数:
        df: 包含价格和成交量数据的DataFrame
        window: 计算窗口大小，默认24个数据点
    
    返回:
        float: 价格变化率与成交量变化率的相关系数
    """
    w = min(len(df), window)
    r = df['close'].pct_change().fillna(0).tail(w)  # 价格变化率
    v = df['volume'].pct_change().fillna(0).tail(w)  # 成交量变化率
    if r.std()==0 or v.std()==0:
        return 0.0  # 标准差为0时返回0，避免除零错误
    return float(r.corr(v))  # 计算皮尔逊相关系数


def price_structure_slopes(df):
    """
    计算价格结构斜率（高点和低点的趋势斜率）
    
    参数:
        df: 包含价格数据的DataFrame
    
    返回:
        tuple: (高点斜率, 低点斜率) 分别表示最高价和最低价的趋势斜率
    """
    # 将分钟级数据重采样为小时级，取每小时的最高价和最低价
    highs = df['high'].resample('1h').max().dropna()
    lows = df['low'].resample('1h').min().dropna()
    
    def slope(s):
        """计算时间序列的线性回归斜率"""
        if len(s) < 3: return 0.0  # 数据点不足时返回0
        x = np.arange(len(s))
        return float(np.polyfit(x, s.values, 1)[0])  # 线性回归斜率
    
    # 计算最近24小时的高点和低点斜率
    return slope(highs[-24:]), slope(lows[-24:])


def score_and_decide(df, signals):
    """
    综合评分和牛熊判定逻辑
    
    参数:
        df: 包含技术指标数据的DataFrame
        signals: 包含市场信号数据的字典
    
    返回:
        dict: 包含评分、判定结果、原因和各项指标的字典
    """
    score = 0  # 初始评分
    reasons = []  # 记录评分原因
    
    # 获取最新价格和移动平均线值
    last_close = float(df['close'].iloc[-1])
    ma_s = float(df['ma_short'].iloc[-1])
    ma_l = float(df['ma_long'].iloc[-1])

    # 1. 价格与长期移动平均线关系（权重：2分）
    if last_close > ma_l:
        score += 2; reasons.append('price_above_ma_long')  # 价格在长期均线上方，看涨
    else:
        score -= 2; reasons.append('price_below_ma_long')  # 价格在长期均线下方，看跌

    # 2. 短期与长期移动平均线关系（权重：1分）
    if ma_s > ma_l:
        score += 1; reasons.append('ma_short_above_long')  # 短期均线在长期均线上方，看涨
    else:
        score -= 1; reasons.append('ma_short_below_long')  # 短期均线在长期均线下方，看跌

    # 3. 价格结构斜率分析（权重：1分）
    hs, ls = price_structure_slopes(df)
    if hs>0 and ls>0:
        score += 1; reasons.append('higher_highs_higher_lows')  # 高点更高、低点更高，看涨
    elif hs<0 and ls<0:
        score -= 1; reasons.append('lower_highs_lower_lows')  # 高点更低、低点更低，看跌

    # 4. 量价相关性分析（权重：1分）
    vpc = vp_corr(df)
    if vpc > 0.1:
        score += 1; reasons.append('volume_price_positive_corr')  # 量价正相关，看涨
    elif vpc < -0.1:
        score -= 1; reasons.append('volume_price_negative_corr')  # 量价负相关，看跌

    # 5. 资金费率信号（权重：1分）
    fr = signals.get('funding_rate')
    sc = signals.get('stablecoin_flow')
    if fr is not None:
        if float(fr) > 0:
            score += 1; reasons.append('positive_funding')  # 正资金费率，看涨
        else:
            score -= 1; reasons.append('negative_funding')  # 负资金费率，看跌
    
    # 6. 稳定币流入信号（权重：1分）
    if sc is not None:
        if float(sc) > 0:
            score += 1; reasons.append('stablecoin_inflow')  # 稳定币流入，看涨
        else:
            score -= 1; reasons.append('stablecoin_outflow')  # 稳定币流出，看跌

    # 根据总分判定牛熊状态
    phase = 'Neutral'  # 中性状态
    if score >= 3:
        phase = 'Bull'  # 牛市：总分≥3
    elif score <= -3:
        phase = 'Bear'  # 熊市：总分≤-3

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



def save_bull_bear_result(engine, exchange, symbol, result):
    """
    保存牛熊判定结果到数据库
    
    参数:
        engine: 数据库引擎
        exchange: 交易所名称
        symbol: 交易对符号
        result: 牛熊判定结果字典
    
    返回:
        bool: 保存成功返回True，失败返回False
    """
    try:
        # 构建插入SQL语句
        sql = text('''
            INSERT INTO indecator_bull_bear (
                exchange, symbol, datetime, score, phase, last_close,
                ma_short, ma_long, vp_corr, funding_rate, stablecoin_flow, reasons
            ) VALUES (
                :exchange, :symbol, :datetime, :score, :phase, :last_close,
                :ma_short, :ma_long, :vp_corr, :funding_rate, :stablecoin_flow, :reasons
            )
            ON CONFLICT (exchange, symbol, datetime) DO UPDATE SET
                score = EXCLUDED.score,
                phase = EXCLUDED.phase,
                last_close = EXCLUDED.last_close,
                ma_short = EXCLUDED.ma_short,
                ma_long = EXCLUDED.ma_long,
                vp_corr = EXCLUDED.vp_corr,
                funding_rate = EXCLUDED.funding_rate,
                stablecoin_flow = EXCLUDED.stablecoin_flow,
                reasons = EXCLUDED.reasons,
                updated_at = now()
        ''')
        
        # 准备参数
        params = {
            'exchange': exchange,
            'symbol': symbol,
            'datetime': datetime.utcnow(),  # 使用当前时间作为判定时间点
            'score': result['score'],
            'phase': result['phase'],
            'last_close': result['last_close'],
            'ma_short': result['ma_short'],
            'ma_long': result['ma_long'],
            'vp_corr': result['vp_corr'],
            'funding_rate': result['funding_rate'],
            'stablecoin_flow': result['stablecoin_flow'],
            'reasons': json.dumps(result['reasons'])  # 将列表转换为JSON字符串
        }
        
        # 执行插入操作
        with engine.begin() as conn:
            conn.execute(sql, params)
        
        logger.info(f"牛熊判定结果已保存到数据库: {exchange}-{symbol}")
        return True
        
    except Exception as e:
        logger.error(f"保存牛熊判定结果失败: {e}")
        return False


def main():
    """
    主函数：执行牛熊判定流程
    
    流程:
        1. 配置参数（交易所、交易对、数据表等）
        2. 获取K线数据
        3. 计算技术指标
        4. 获取市场信号
        5. 进行综合评分和牛熊判定
        6. 保存判定结果到数据库
    """
    # 配置参数
    exchange = 'binance'  # 交易所
    symbol = 'binance-BTC/USDT'  # 交易对符号（数据库格式）
    norm_symbol = 'BTCUSDT'  # 标准化交易对符号
    kline_table = 'market_minute_klines'  # K线数据表名
    lookback_hours = 48  # 回溯小时数
    ma_short = 50  # 短期移动平均窗口
    ma_long = 200  # 长期移动平均窗口

    # 获取K线数据
    df = fetch_klines(engine, kline_table, exchange, symbol, lookback_hours)
    
    # 计算移动平均线指标
    df = compute_mas(df, ma_short, ma_long)

    # 获取最新的市场信号数据
    signals = fetch_latest_signals(engine, exchange, norm_symbol)
    
    # 进行综合评分和牛熊判定
    result = score_and_decide(df, signals)
    
    # 记录判定结果
    logger.info(f"判定结果: {result}")
    
    # 保存判定结果到数据库
    save_success = save_bull_bear_result(engine, exchange, symbol, result)
    if save_success:
        logger.info(f"牛熊判定结果已成功保存到数据库")
    else:
        logger.error(f"牛熊判定结果保存失败")

   

if __name__ == '__main__':
    main()