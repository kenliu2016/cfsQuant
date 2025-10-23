#!/usr/bin/env python3
"""
HMM定时任务执行脚本
支持不同周期的HMM分析执行
"""

import os
import sys
import pandas as pd
import psycopg2
import numpy as np
from datetime import datetime, timedelta
from hmmlearn.hmm import GaussianHMM
import joblib

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.logger import LoggerFactory
from common.db import get_engine

logger = LoggerFactory.get_logger("indecator.hmm_schedule")

# === 数据库连接 ===
engine = get_engine()

# === 周期配置 ===
PERIOD_CONFIGS = {
    'high_frequency': {
        'tables': ['market_ohlcv_1m', 'market_ohlcv_5m', 'market_ohlcv_15m', 'market_ohlcv_30m'],
        'description': '高频周期 (1分钟, 5分钟, 15分钟, 30分钟)',
        'data_lookback_days': 7  # 7天数据
    },
    'medium_frequency': {
        'tables': ['market_ohlcv_1h', 'market_ohlcv_2h', 'market_ohlcv_4h'],
        'description': '中频周期 (1小时, 2小时, 4小时)',
        'data_lookback_days': 30  # 30天数据
    },
    'low_frequency': {
        'tables': ['market_ohlcv_1d', 'market_ohlcv_2d', 'market_ohlcv_3d', 'market_ohlcv_3m'],
        'description': '低频周期 (1天, 2天, 3天, 3个月)',
        'data_lookback_days': 365  # 1年数据
    }
}

# === 获取活跃的USDT交易对 ===
def get_active_usdt_symbols():
    """从market_codes表中获取所有活跃的USDT交易对"""
    query = """
    SELECT exchange, code 
    FROM market_codes 
    WHERE active = true AND quotecurrency = 'USDT' 
    ORDER BY exchange, code
    """
    try:
        df = pd.read_sql(query, engine)
        logger.info(f"获取到 {len(df)} 个活跃USDT交易对")
        return df
    except Exception as e:
        logger.error(f"获取活跃USDT交易对时出错: {e}")
        return pd.DataFrame()

# === 获取指定周期的K线数据 ===
def get_ohlcv_for_period(table, exchange, symbol, lookback_days=None):
    """获取指定周期的K线数据，支持数据回溯"""
    # 根据表名确定时间字段
    if table == 'market_ohlcv_1m':
        time_field = 'datetime'
    else:
        time_field = 'bucket'
    
    query = f"SELECT {time_field}, close FROM {table} WHERE exchange='{exchange}' AND symbol='{symbol}'"
    
    if lookback_days:
        start_date = datetime.now() - timedelta(days=lookback_days)
        query += f" AND {time_field} >= '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'"
    
    query += f" ORDER BY {time_field} ASC"
    
    try:
        df = pd.read_sql(query, engine, parse_dates=[time_field])
        df.set_index(time_field, inplace=True)
        return df
    except Exception as e:
        logger.error(f"获取 {table} {symbol} 数据时出错: {e}")
        return pd.DataFrame()

# === 计算对数收益率 ===
def compute_returns(df):
    """计算对数收益率"""
    if len(df) < 2:
        return df
    df['returns'] = np.log(df['close'] / df['close'].shift(1))
    return df.dropna()

# === 训练或加载 HMM 模型 ===
def load_or_train_hmm(df_returns, model_file):
    """训练或加载HMM模型"""
    try:
        hmm = joblib.load(model_file)
        logger.info(f"加载HMM模型从 {model_file}")
    except:
        hmm = GaussianHMM(n_components=2, covariance_type='full', n_iter=1000, random_state=42)
        hmm.fit(df_returns['returns'].values.reshape(-1,1))
        joblib.dump(hmm, model_file)
        logger.info(f"模型训练完成，状态数: {hmm.n_components}")
    return hmm

# === 生成信号和仓位 ===
def generate_signal(hmm, df_returns):
    """生成HMM信号和仓位"""
    X = df_returns['returns'].values.reshape(-1,1)
    probs = hmm.predict_proba(X)
    latest_prob = probs[-1, 1]  # state=1 为高波动/趋势
    if latest_prob > 0.6:
        return "多 (7:3)", 0.7, [1-latest_prob, latest_prob]
    elif latest_prob < 0.4:
        return "空 (3:7)", -0.7, [1-latest_prob, latest_prob]
    else:
        return "中性 (5:5)", 0.0, [1-latest_prob, latest_prob]

# === 写入 PostgreSQL ===
def save_signal(exchange, symbol, timeframe, dt, state_prob, signal, position):
    """保存HMM信号到数据库"""
    df = pd.DataFrame([{
        'exchange': exchange,
        'code': symbol,
        'timeframe': timeframe,
        'datetime': dt,
        'state_prob_0': state_prob[0],
        'state_prob_1': state_prob[1],
        'signal': signal,
        'position': position,
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    }])
    df.to_sql('indecator_hmm', engine, if_exists='append', index=False)

# === 执行指定周期的HMM分析 ===
def run_hmm_for_period(period_type, symbols_limit=None):
    """执行指定周期的HMM分析"""
    config = PERIOD_CONFIGS[period_type]
    logger.info(f"开始执行 {config['description']} HMM分析")
    
    # 获取交易对
    symbols_df = get_active_usdt_symbols()
    if symbols_df.empty:
        logger.error("未找到活跃的USDT交易对")
        return
    
    # 限制处理数量（用于测试）
    if symbols_limit:
        symbols_df = symbols_df.head(symbols_limit)
    
    total_symbols = len(symbols_df)
    processed_count = 0
    success_count = 0
    
    for index, row in symbols_df.iterrows():
        exchange = row['exchange']
        symbol = row['code']
        processed_count += 1
        
        logger.info(f"处理进度: {processed_count}/{total_symbols} - {exchange} - {symbol}")
        
        for table in config['tables']:
            try:
                # 获取数据
                df = get_ohlcv_for_period(table, exchange, symbol, config['data_lookback_days'])
                if df.empty:
                    logger.warning(f"{table} {symbol} 无数据")
                    continue
                
                # 检查数据量
                if len(df) < 2:
                    logger.warning(f"{table} {symbol} 数据量不足")
                    continue
                
                # 计算收益率
                df_returns = compute_returns(df)
                if len(df_returns) < 2:
                    logger.warning(f"{table} {symbol} 收益率数据不足")
                    continue
                
                # HMM 模型文件名（区分周期），保存到hmmModel目录
                model_file = os.path.join("hmmModel", f"hmm_model_{symbol.replace('/','_')}_{period_type}_{table}.pkl")
                
                # 训练或加载 HMM 模型
                try:
                    hmm = load_or_train_hmm(df_returns, model_file)
                except Exception as e:
                    logger.error(f"{table} {symbol} HMM模型训练失败: {e}")
                    continue
                
                # 生成信号
                signal, position, state_prob = generate_signal(hmm, df_returns)
                dt = df_returns.index[-1]
                
                # 写入 PostgreSQL
                save_signal(exchange, symbol, period_type, dt, state_prob, signal, position)
                logger.info(f"[{period_type}] {table} {exchange} - {symbol} {dt} => 信号: {signal}, 仓位: {position}, 概率: {state_prob[1]:.2f}")
                
                success_count += 1
                logger.info(f"成功处理 {table} {symbol}")
                
            except Exception as e:
                logger.error(f"处理 {table} {symbol} 时出错: {e}")
                continue
    
    logger.info(f"{config['description']} HMM分析完成: 成功处理 {success_count} 个交易对周期")

# === 主执行函数 ===
def main():
    """主执行函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HMM定时任务执行脚本')
    parser.add_argument('--period', type=str, choices=['high', 'medium', 'low', 'all'], 
                       default='all', help='执行周期类型: high(高频), medium(中频), low(低频), all(全部)')
    parser.add_argument('--limit', type=int, default=None, help='限制处理的交易对数量（用于测试）')
    
    args = parser.parse_args()
    
    logger.info(f"开始执行HMM定时任务，周期: {args.period}, 限制: {args.limit}")
    
    if args.period == 'all':
        periods = ['high_frequency', 'medium_frequency', 'low_frequency']
    elif args.period == 'high':
        periods = ['high_frequency']
    elif args.period == 'medium':
        periods = ['medium_frequency']
    elif args.period == 'low':
        periods = ['low_frequency']
    
    for period in periods:
        run_hmm_for_period(period, args.limit)
    
    logger.info("HMM定时任务执行完成")

if __name__ == "__main__":
    import numpy as np  # 确保numpy被导入
    main()