#!/usr/bin/env python3
"""
HMM定时任务执行脚本
支持不同周期的HMM分析执行
集成优化的HMM模型训练器
"""

import os
import sys
import pandas as pd
import psycopg2
import numpy as np
from datetime import datetime, timedelta
from hmmlearn.hmm import GaussianHMM
import joblib
from sqlalchemy import text

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
hmm_auto_training_dir = os.path.join(current_dir, 'hmm_auto_training')
sys.path.insert(0, backend_dir)
sys.path.insert(0, hmm_auto_training_dir)
sys.path.insert(0, current_dir)
from common.logger import LoggerFactory
from common.db import get_engine


logger = LoggerFactory.get_logger("indecator.hmm_schedule")

# === 数据库连接 ===
engine = get_engine()

# === 模型目录 ===
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hmmModel")
os.makedirs(MODEL_DIR, exist_ok=True)

# === 周期配置 ===
PERIOD_CONFIGS = {
    'high_frequency': {
        'tables': ['market_ohlcv_1m', 'market_ohlcv_3m','market_ohlcv_5m', 'market_ohlcv_15m', 'market_ohlcv_30m'],
        'description': '高频周期 (1分钟, 3分钟, 5分钟, 15分钟, 30分钟)',
        'data_lookback_days': 7  # 7天数据
    },
    'medium_frequency': {
        'tables': ['market_ohlcv_1h', 'market_ohlcv_2h', 'market_ohlcv_4h'],
        'description': '中频周期 (1小时, 2小时, 4小时)',
        'data_lookback_days': 30  # 30天数据
    },
    'low_frequency': {
        'tables': ['market_ohlcv_1d', 'market_ohlcv_2d', 'market_ohlcv_3d'],
        'description': '低频周期 (1天, 2天, 3天)',
        'data_lookback_days': 365  # 1年数据
    }
}

# === 获取活跃的USDT交易对 ===
def get_active_usdt_symbols():
    """从market_codes表中获取所有活跃的USDT交易对"""
    query = """
    SELECT exchange, symbol 
    FROM market_codes 
    WHERE active = true AND quotecurrency = 'USDT' 
    ORDER BY exchange, symbol
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
    time_field = 'datetime' if table == 'market_ohlcv_1m' else 'bucket'
    ts_alias = 'price_time'
    
    sql = f"""
        SELECT {time_field} AS {ts_alias}, close
        FROM {table}
        WHERE exchange = :exchange AND symbol = :symbol
    """
    
    params = {'exchange': exchange, 'symbol': symbol}
    
    if lookback_days:
        start_date = datetime.utcnow() - timedelta(days=lookback_days)
        sql += f" AND {time_field} >= :start_date"
        params['start_date'] = start_date
    
    sql += f" ORDER BY {time_field} ASC"
    
    try:
        df = pd.read_sql(text(sql), engine, params=params, parse_dates=[ts_alias])
        if df.empty:
            return df
        df = df.rename(columns={ts_alias: 'datetime'})
        df.set_index('datetime', inplace=True)
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

# === 缓存既有信号 ===
def load_existing_signal_map(timeframes):
    """加载指定时间框架的最新信号时间"""
    if not timeframes:
        return {}
    params = {f"tf{i}": tf for i, tf in enumerate(timeframes)}
    placeholders = ", ".join(f":tf{i}" for i in range(len(timeframes)))
    sql = text(f"""
        SELECT exchange, symbol, timeframe, MAX(datetime) AS last_dt
        FROM indecator_hmm
        WHERE timeframe IN ({placeholders})
        GROUP BY exchange, symbol, timeframe
    """)
    try:
        df = pd.read_sql(sql, engine, params=params, parse_dates=['last_dt'])
    except Exception as e:
        logger.error(f"加载历史HMM结果失败: {e}")
        return {}
    cache = {}
    for _, row in df.iterrows():
        cache[(row['exchange'], row['symbol'], row['timeframe'])] = row['last_dt']
    return cache

# === 训练或加载 HMM 模型 ===
def load_or_train_hmm(df_returns, model_file):
    """训练或加载HMM模型（使用优化器版本）"""
    try:
        # 尝试加载现有模型
        hmm = joblib.load(model_file)
        logger.info(f"加载HMM模型从 {model_file}")
        
        # 验证模型质量
        X = df_returns['returns'].values.reshape(-1,1)
        try:
            probs = hmm.predict_proba(X)
            # 检查状态概率分布是否合理
            avg_prob_0 = probs[:, 0].mean()
            avg_prob_1 = probs[:, 1].mean()
            
            # 如果状态概率过于极端，重新训练模型
            if avg_prob_0 > 0.95 or avg_prob_1 > 0.95:
                logger.warning(f"模型状态概率分布异常 (avg_prob_0={avg_prob_0:.3f}, avg_prob_1={avg_prob_1:.3f})，重新训练模型")
                raise Exception("模型状态概率分布异常")
                
        except Exception as e:
            logger.warning(f"模型验证失败: {e}，重新训练模型")
            raise Exception("模型验证失败")
            
    except:
        # 使用优化的HMM模型训练器
        logger.info("使用优化的HMM模型训练器进行训练")
        
        # 创建优化器实例
        optimizer = HMMModelOptimizer()
        
        # 准备训练数据
        returns_data = df_returns['returns'].values.reshape(-1, 1)
        
        # 使用优化器创建HMM模型
        hmm = optimizer.create_optimized_hmm()
        
        # 智能初始化参数
        optimizer.initialize_model_parameters(hmm, returns_data.flatten())
        
        # 带收敛性监控的训练
        training_results = optimizer.train_with_convergence_monitoring(hmm, returns_data)
        
        # 记录训练结果
        if training_results['converged']:
            logger.info(f"模型训练成功，迭代次数: {training_results['iterations_used']}")
        else:
            logger.warning(f"模型训练未完全收敛，警告: {training_results['warnings']}")
        
        # 保存优化后的模型
        joblib.dump(hmm, model_file)
        logger.info(f"优化HMM模型训练完成并保存到 {model_file}")
        
    return hmm

# === 生成信号和仓位 ===
def generate_signal(hmm, df_returns):
    """生成HMM信号和仓位（优化版本）"""
    X = df_returns['returns'].values.reshape(-1,1)
    
    # 预测状态序列
    states = hmm.predict(X)
    
    # 计算状态概率
    probs = hmm.predict_proba(X)
    
    # 检查状态概率分布
    avg_prob_0 = probs[:, 0].mean()
    avg_prob_1 = probs[:, 1].mean()
    
    # 如果状态概率过于极端，发出警告
    if avg_prob_0 > 0.85 or avg_prob_1 > 0.85 or avg_prob_0 < 0.15 or avg_prob_1 < 0.15:
        logger.warning(f"HMM状态概率分布异常: avg_prob_0={avg_prob_0:.3f}, avg_prob_1={avg_prob_1:.3f}")
    
    # 检查状态切换频率
    state_changes = np.sum(np.diff(states) != 0)
    total_periods = len(states) - 1
    change_rate = state_changes / total_periods if total_periods > 0 else 0
    
    # 获取最新状态和概率
    current_state = states[-1]
    current_prob_0 = probs[-1, 0]
    current_prob_1 = probs[-1, 1]
    
    # 计算状态稳定性指标
    recent_states = states[-10:] if len(states) >= 10 else states
    state_stability = len(set(recent_states)) / len(recent_states)  # 状态多样性指标
    
    # 计算概率置信度
    prob_confidence = max(current_prob_0, current_prob_1)
    
    # 改进的信号生成逻辑
    signal = "中性"
    position = 0
    
    # 条件1: 状态切换频率控制 (放宽阈值)
    if change_rate > 0.6:  # 从0.5放宽到0.6
        signal = "中性(切换频繁)"
        position = 0
        logger.warning(f"状态切换频率过高:{state_changes}次切换, 切换率:{change_rate:.3f}")
    
    # 条件2: 概率置信度控制
    elif prob_confidence < 0.6:  # 置信度不足
        signal = "中性(低置信度)"
        position = 0
    
    # 条件3: 状态稳定性控制
    elif state_stability > 0.5:  # 近期状态不稳定
        signal = "中性(状态不稳定)"
        position = 0
    
    # 条件4: 极端概率控制
    elif current_prob_0 > 0.8 or current_prob_1 > 0.8:
        # 极端概率时采用保守策略
        if current_state == 0 and current_prob_0 > 0.8:
            signal = "空(高置信度)"
            position = -0.5  # 减半仓位
        elif current_state == 1 and current_prob_1 > 0.8:
            signal = "多(高置信度)"
            position = 0.5   # 减半仓位
        else:
            signal = "中性(极端概率)"
            position = 0
    
    # 条件5: 正常信号生成
    else:
        if current_state == 0 and current_prob_0 > 0.55:
            signal = "空"
            position = -1
        elif current_state == 1 and current_prob_1 > 0.55:
            signal = "多"
            position = 1
        else:
            signal = "中性"
            position = 0
    
    # 记录信号质量评估
    signal_quality = "高"
    if signal.startswith("中性"):
        signal_quality = "低"
    elif "高置信度" in signal:
        signal_quality = "中"
    
    logger.info(f"信号生成: {signal}, 仓位: {position}, 置信度: {prob_confidence:.3f}, 质量: {signal_quality}")
    
    return signal, position, [current_prob_0, current_prob_1]

# === 写入 PostgreSQL ===
def save_signal(exchange, symbol, timeframe, datetime, signal, position, state_prob_0, state_prob_1):
    """保存HMM信号到数据库（增强版本）"""
    
    # 数据质量检查
    if state_prob_0 + state_prob_1 != 1.0:
        logger.warning(f"状态概率和不等于1: {state_prob_0} + {state_prob_1} = {state_prob_0 + state_prob_1}")
        # 归一化处理
        total = state_prob_0 + state_prob_1
        state_prob_0 = state_prob_0 / total
        state_prob_1 = state_prob_1 / total
    
    # 检查是否已有该时间点的记录
    existing_query = f"""
    SELECT id FROM indecator_hmm 
    WHERE exchange = '{exchange}' AND symbol = '{symbol}' 
    AND timeframe = '{timeframe}' AND datetime = '{datetime}'
    """
    
    existing_df = pd.read_sql(existing_query, engine)
    
    if len(existing_df) > 0:
        # 更新现有记录
        update_query = f"""
        UPDATE indecator_hmm 
        SET signal = '{signal}', position = {position}, 
            state_prob_0 = {state_prob_0}, state_prob_1 = {state_prob_1},
            updated_at = NOW()
        WHERE id = {existing_df.iloc[0]['id']}
        """
        with engine.connect() as conn:
            conn.execute(text(update_query))
            conn.commit()
        logger.info(f"更新HMM信号: {exchange} {symbol} {timeframe} {datetime}")
    else:
        # 插入新记录
        insert_query = f"""
        INSERT INTO indecator_hmm 
        (exchange, symbol, timeframe, datetime, signal, position, 
         state_prob_0, state_prob_1, created_at, updated_at)
        VALUES 
        ('{exchange}', '{symbol}', '{timeframe}', '{datetime}', '{signal}', {position},
         {state_prob_0}, {state_prob_1}, NOW(), NOW())
        """
        with engine.connect() as conn:
            conn.execute(text(insert_query))
            conn.commit()
        logger.info(f"插入HMM信号: {exchange} {symbol} {timeframe} {datetime}")
    
    # 记录数据质量指标
    if state_prob_1 < 0.01 or state_prob_1 > 0.99:
        logger.warning(f"极端概率记录: {exchange} {symbol} {timeframe} - prob_1={state_prob_1:.6f}")
    
    return True


def generate_hmm_quality_report():
    """生成HMM模型质量报告"""
    from common.db import get_engine
    import pandas as pd
    
    engine = get_engine()
    
    # 查询数据质量指标
    quality_query = """
    SELECT 
        COUNT(*) as total_records,
        SUM(CASE WHEN state_prob_1 < 0.01 OR state_prob_1 > 0.99 THEN 1 ELSE 0 END) as extreme_prob_count,
        SUM(CASE WHEN signal LIKE '%%模型异常%%' THEN 1 ELSE 0 END) as model_error_count,
        AVG(state_prob_1) as avg_prob_1,
        STDDEV(state_prob_1) as std_prob_1,
        COUNT(DISTINCT signal) as unique_signal_count
    FROM indecator_hmm
    """
    
    quality_df = pd.read_sql(quality_query, engine)
    
    if len(quality_df) > 0:
        row = quality_df.iloc[0]
        extreme_ratio = row['extreme_prob_count'] / row['total_records'] if row['total_records'] > 0 else 0
        error_ratio = row['model_error_count'] / row['total_records'] if row['total_records'] > 0 else 0
        
        logger.info(f"=== HMM模型质量报告 ===")
        logger.info(f"总记录数: {row['total_records']}")
        logger.info(f"极端概率比例: {extreme_ratio:.2%}")
        logger.info(f"模型异常比例: {error_ratio:.2%}")
        logger.info(f"平均状态概率: {row['avg_prob_1']:.4f}")
        logger.info(f"状态概率标准差: {row['std_prob_1']:.4f}")
        logger.info(f"唯一信号类型: {row['unique_signal_count']}")
        
        # 质量评估
        if extreme_ratio > 0.3:
            logger.warning("⚠️ 极端概率比例过高，建议检查模型训练")
        if error_ratio > 0.1:
            logger.warning("⚠️ 模型异常比例过高，建议优化数据预处理")
        if row['std_prob_1'] < 0.1:
            logger.warning("⚠️ 状态概率分布过于集中，可能模型失效")
            
        logger.info(f"=== 报告结束 ===")
    
    return quality_df

# === 执行指定周期的HMM分析 ===
def run_hmm_for_period(period_type, symbols_limit=None):
    """执行指定周期的HMM分析"""
    config = PERIOD_CONFIGS[period_type]
    logger.info(f"开始执行 {config['description']} HMM分析")

    target_timeframes = [table.replace('market_ohlcv_', '') for table in config['tables']]
    latest_signal_map = load_existing_signal_map(target_timeframes)
    
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
        symbol = row['symbol']
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
                
                # HMM 模型文件名（区分周期），保存到模型目录
                actual_timeframe = table.replace('market_ohlcv_', '')
                latest_dt = df_returns.index[-1].to_pydatetime()
                
                cache_key = (exchange, symbol, actual_timeframe)
                existing_dt = latest_signal_map.get(cache_key)
                
                # 修复时区比较问题：确保两个datetime对象都是naive或aware
                if existing_dt is not None and not pd.isna(existing_dt):
                    # 将existing_dt转换为naive datetime（如果它是aware）
                    if hasattr(existing_dt, 'tzinfo') and existing_dt.tzinfo is not None:
                        existing_py_dt = existing_dt.replace(tzinfo=None)
                    else:
                        existing_py_dt = existing_dt
                else:
                    existing_py_dt = None
                    
                # 确保latest_dt也是naive datetime
                if hasattr(latest_dt, 'tzinfo') and latest_dt.tzinfo is not None:
                    latest_dt = latest_dt.replace(tzinfo=None)
                    
                if existing_py_dt is not None and latest_dt <= existing_py_dt:
                    logger.info(f"[{actual_timeframe}] {exchange}-{symbol} 已有最新HMM结果，跳过")
                    continue
                
                model_file = os.path.join(MODEL_DIR, f"hmm_model_{symbol.replace('/','_')}_{actual_timeframe}.pkl")
                
                # 训练或加载 HMM 模型
                try:
                    hmm = load_or_train_hmm(df_returns, model_file)
                except Exception as e:
                    logger.error(f"{table} {symbol} HMM模型训练失败: {e}")
                    continue
                
                # 生成信号
                signal, position, state_prob = generate_signal(hmm, df_returns)
                dt = latest_dt
                
                # 写入 PostgreSQL
                save_signal(exchange, symbol, actual_timeframe, dt, signal, position, state_prob[0], state_prob[1])
                latest_signal_map[cache_key] = pd.Timestamp(dt)
                logger.info(f"[{actual_timeframe}] {exchange} - {symbol} {dt} => 信号: {signal}, 仓位: {position}, 概率: {state_prob[1]:.2f}")
                
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
