import numpy as np
import pandas as pd
import psycopg2
from hmmlearn.hmm import GaussianHMM
import joblib
from datetime import datetime
import sys
import os

# 添加项目根目录到Python路径，以便能够导入app模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.logger import LoggerFactory

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("indecator.hmm")

from common.db import get_engine

# === PostgreSQL 连接 ===
engine = get_engine()

# === 获取 K 线数据函数 ===
def get_ohlcv(table, exchange, symbol, start_date=None):
    # 根据表名确定时间字段
    # 只有1分钟表使用datetime字段，其他表使用bucket字段
    if table == 'market_ohlcv_1m':
        time_field = 'datetime'
    else:
        time_field = 'bucket'
    
    query = f"SELECT {time_field}, close FROM {table} WHERE exchange='{exchange}' AND symbol='{symbol}'"
    if start_date:
        query += f" AND {time_field} >= '{start_date}'"
    query += f" ORDER BY {time_field} ASC"
    df = pd.read_sql(query, engine, parse_dates=[time_field])
    df.set_index(time_field, inplace=True)
    return df

# === 计算对数收益率 ===
def compute_returns(df):
    df['returns'] = np.log(df['close'] / df['close'].shift(1))
    return df.dropna()

# === 训练或加载 HMM 模型 ===
def load_or_train_hmm(df_returns, model_file):
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

# === 主流程函数 ===
def run_hmm_signal(exchange, symbol):
    # 定义所有要分析的OHLCV表
    tables = ['market_ohlcv_1m','market_ohlcv_5m','market_ohlcv_15m','market_ohlcv_30m',
              'market_ohlcv_1h','market_ohlcv_2h','market_ohlcv_4h','market_ohlcv_1d',
              'market_ohlcv_2d','market_ohlcv_3d','market_ohlcv_3m']
    
    for table in tables:
        # 获取数据
        df = get_ohlcv(table, exchange, symbol)
        if df.empty:
            logger.warning(f"{table} {symbol} 无数据")
            continue
        
        # 检查数据量是否足够（至少需要2个样本才能训练HMM模型）
        if len(df) < 2:
            logger.warning(f"{table} {symbol} 数据量不足 ({len(df)}条记录)，跳过HMM分析")
            continue
            
        df_returns = compute_returns(df)
        
        # 检查收益率数据量是否足够（至少需要2个收益率样本）
        if len(df_returns) < 2:
            logger.warning(f"{table} {symbol} 收益率数据量不足 ({len(df_returns)}条记录)，跳过HMM分析")
            continue
        
        # HMM 模型文件名（区分周期），保存到hmmModel目录
        model_file = os.path.join("hmmModel", f"hmm_model_{symbol.replace('/','_')}_{table}.pkl")
        
        try:
            hmm = load_or_train_hmm(df_returns, model_file)
            
            # 生成信号
            signal, position, state_prob = generate_signal(hmm, df_returns)
            dt = df_returns.index[-1]
            
            # 写入 PostgreSQL
            save_signal(exchange, symbol, table.replace('_realtime',''), dt, state_prob, signal, position)
            logger.info(f"[{table}] {symbol} {dt} => 信号: {signal}, 仓位: {position}, 概率: {state_prob[1]:.2f}")
        except Exception as e:
            logger.error(f"{table} {symbol} HMM分析失败: {e}")
            continue

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
        return df
    except Exception as e:
        logger.error(f"获取活跃USDT交易对时出错: {e}")
        return pd.DataFrame()

# === 运行示例 ===
if __name__ == "__main__":
    # 获取所有活跃的USDT交易对
    symbols_df = get_active_usdt_symbols()
    
    if symbols_df.empty:
        logger.error("未找到活跃的USDT交易对")
    else:
        logger.info(f"开始处理 {len(symbols_df)} 个活跃USDT交易对的HMM分析")
        
        # 遍历所有交易对进行HMM分析
        for index, row in symbols_df.iterrows():
            exchange = row['exchange']
            symbol = row['code']
            logger.info(f"正在处理: {exchange} - {symbol}")
            
            try:
                run_hmm_signal(exchange=exchange, symbol=symbol)
            except Exception as e:
                logger.error(f"处理 {exchange} - {symbol} 时出错: {e}")
                continue
        
        logger.info("所有交易对的HMM分析完成")
