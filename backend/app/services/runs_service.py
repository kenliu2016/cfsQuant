
import pandas as pd
from ..db import fetch_df

def recent_runs(limit: int = 20) -> pd.DataFrame:
    sql = """
    SELECT run_id, strategy, code, start_time, end_time, initial_capital, final_capital, created_at
    FROM runs ORDER BY start_time DESC LIMIT :limit
    """
    return fetch_df(sql, limit=limit)

import logging
import datetime
import json

logger = logging.getLogger(__name__)

def run_detail(run_id: str):
    
    # 获取基本回测信息，包含新增的paras字段
    df_run = fetch_df("""SELECT run_id, strategy, code, start_time, end_time, initial_capital, final_capital, created_at, paras
                         FROM runs WHERE run_id=:rid""", rid=run_id)
    
    # 日志记录查询结果
    if df_run.empty:
        logger.warning(f"未找到run_id为{run_id}的回测记录")
        # 返回默认的回测信息，避免前端显示为空
        # 确保所有值都是可JSON序列化的类型
        default_run_info = {
            "run_id": run_id,
            "strategy": "未知策略",
            "code": "未知标的",
            "start_time": "",
            "end_time": "",
            "initial_capital": 0.0,
            "final_capital": 0.0,
            "created_at": datetime.datetime.now().isoformat(),
            "paras": {}
        }
        return {
            "info": default_run_info,
            "metrics": [],
            "equity": [],
            "trades": []
        }
    
    # 获取指标数据
    df_m = fetch_df("SELECT metric_name, metric_value FROM metrics WHERE run_id=:rid", rid=run_id)
    # 从equity_curve表读取数据，equity_curve表全面取代equity表
    df_e = fetch_df("SELECT datetime, nav, drawdown FROM equity_curve WHERE run_id=:rid ORDER BY datetime", rid=run_id)
    # 获取交易记录数据
    df_t = fetch_df("""
        SELECT run_id, datetime, code, side, price, qty, amount, fee, realized_pnl, nav
        FROM trades
        WHERE run_id = :rid
        ORDER BY datetime
    """, rid=run_id)
    
    # 确保返回的数据是可JSON序列化的
    run_info = df_run.iloc[0].to_dict()
    
    # 转换datetime类型为字符串
    for key in ['start_time', 'end_time', 'created_at']:
        if key in run_info and isinstance(run_info[key], datetime.datetime):
            run_info[key] = run_info[key].isoformat()
        elif key in run_info and run_info[key] is None:
            run_info[key] = ""
    
    # 确保数值类型正确
    for key in ['initial_capital', 'final_capital']:
        if key in run_info:
            try:
                run_info[key] = float(run_info[key])
            except (ValueError, TypeError):
                run_info[key] = 0.0
    
    # 处理paras字段，确保它是一个字典
    if 'paras' in run_info:
        try:
            if isinstance(run_info['paras'], str):
                # 如果是字符串，尝试解析为JSON对象
                run_info['paras'] = json.loads(run_info['paras'])
            elif not isinstance(run_info['paras'], dict):
                # 如果不是字典且不是字符串，转换为空字典
                run_info['paras'] = {}
        except (json.JSONDecodeError, TypeError):
            # 如果解析失败，设置为空字典
            run_info['paras'] = {}
    
    # 处理equity数据中的datetime类型和特殊浮点值
    if not df_e.empty:
        # 确保datetime列是字符串类型
        if 'datetime' in df_e.columns:
            df_e['datetime'] = df_e['datetime'].astype(str)
        
        # 处理equity数据中的数值列
        numeric_columns_e = df_e.select_dtypes(include=['float64']).columns
        for col in numeric_columns_e:
            # 将NaN替换为0
            df_e[col] = df_e[col].fillna(0)
            # 将Infinity和-Infinity替换为0
            df_e[col] = df_e[col].replace([float('inf'), float('-inf')], 0)
            # 确保所有值都是可JSON序列化的float类型
            df_e[col] = df_e[col].astype(float)
    
    # 处理metrics数据中的特殊浮点值
    if not df_m.empty:
        # 处理metric_value列
        if 'metric_value' in df_m.columns:
            # 将NaN替换为0
            df_m['metric_value'] = df_m['metric_value'].fillna(0)
            # 将Infinity和-Infinity替换为0
            df_m['metric_value'] = df_m['metric_value'].replace([float('inf'), float('-inf')], 0)
            # 确保所有值都是可JSON序列化的float类型
            df_m['metric_value'] = df_m['metric_value'].astype(float)
    
    # 处理交易记录中的datetime类型和特殊浮点值
    if not df_t.empty:
        # 确保datetime列是字符串类型
        if 'datetime' in df_t.columns:
            df_t['datetime'] = df_t['datetime'].astype(str)
        
        # 处理数值列中的NaN、Infinity和-Infinity等特殊浮点值
        numeric_columns = df_t.select_dtypes(include=['float64']).columns
        for col in numeric_columns:
            # 将NaN替换为0
            df_t[col] = df_t[col].fillna(0)
            # 将Infinity和-Infinity替换为0
            df_t[col] = df_t[col].replace([float('inf'), float('-inf')], 0)
            # 确保所有值都是可JSON序列化的float类型
            df_t[col] = df_t[col].astype(float)
    
    logger.debug(f"成功获取回测详情，run_id: {run_id}, 策略: {run_info.get('strategy', '未知')}")
    
    # 统一返回四部分数据：基本信息、指标数据、equity数据和交易数据
    return {
        "info": run_info,
        "metrics": df_m.to_dict(orient="records"),
        "equity": df_e.to_dict(orient="records"),
        "trades": df_t.to_dict(orient="records")
    }
