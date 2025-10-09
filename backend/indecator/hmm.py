import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
import joblib
from datetime import datetime
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

# === 获取 K 线数据函数 ===
def get_ohlcv(table, exchange, code, start_date=None):
    query = f"SELECT datetime, close FROM {table} WHERE exchange='{exchange}' AND code='{code}'"
    if start_date:
        query += f" AND datetime >= '{start_date}'"
    query += " ORDER BY datetime ASC"
    df = pd.read_sql(query, engine, parse_dates=['datetime'])
    df.set_index('datetime', inplace=True)
    return df

# === 计算对数收益率 ===
def compute_returns(df):
    df['returns'] = np.log(df['close'] / df['close'].shift(1))
    return df.dropna()

# === 训练或加载 HMM 模型 ===
def load_or_train_hmm(df_returns, model_file):
    try:
        hmm = joblib.load(model_file)
        print(f"Loaded HMM model from {model_file}")
    except:
        hmm = GaussianHMM(n_components=2, covariance_type='full', n_iter=1000, random_state=42)
        hmm.fit(df_returns['returns'].values.reshape(-1,1))
        joblib.dump(hmm, model_file)
        print(f"Trained new HMM model and saved to {model_file}")
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
def save_signal(exchange, code, timeframe, dt, state_prob, signal, position):
    df = pd.DataFrame([{
        'exchange': exchange,
        'code': code,
        'timeframe': timeframe,
        'datetime': dt,
        'state_prob_0': state_prob[0],
        'state_prob_1': state_prob[1],
        'signal': signal,
        'position': position,
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    }])
    df.to_sql('hmm_signal_realtime', engine, if_exists='append', index=False)

# === 主流程函数 ===
def run_hmm_signal(exchange, code, tables=['minute_realtime','hour_realtime','day_realtime']):
    for table in tables:
        # 获取数据
        df = get_ohlcv(table, exchange, code)
        if df.empty:
            print(f"No data for {table} {code}")
            continue
        df_returns = compute_returns(df)
        
        # HMM 模型文件名（区分周期）
        model_file = f"hmm_model_{code.replace('/','_')}_{table}.pkl"
        hmm = load_or_train_hmm(df_returns, model_file)
        
        # 生成信号
        signal, position, state_prob = generate_signal(hmm, df_returns)
        dt = df_returns.index[-1]
        
        # 写入 PostgreSQL
        save_signal(exchange, code, table.replace('_realtime',''), dt, state_prob, signal, position)
        print(f"[{table}] {code} {dt} => Signal: {signal}, Position: {position}, Prob: {state_prob[1]:.2f}")

# === 运行示例 ===
if __name__ == "__main__":
    run_hmm_signal(exchange='binance', code='binance-BTC/USDT')
