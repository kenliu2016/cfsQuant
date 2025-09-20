
import pandas as pd
import numpy as np

# 避免Pandas future downcasting警告
pd.set_option('future.no_silent_downcasting', True)
from ..db import fetch_df
import datetime

def recent_runs(limit: int = 20, page: int = 1, code: str = None, strategy: str = None, sortField: str = None, sortOrder: str = None) -> dict:
    """
    获取回测运行记录，支持分页、过滤和排序，包含最大回撤和夏普率指标
    
    Args:
        limit: 每页记录数
        page: 当前页码
        code: 标的代码过滤
        strategy: 策略名称过滤
        sortField: 排序字段
        sortOrder: 排序方向 ('ascend' 或 'descend')
        
    Returns:
        包含记录列表和总数的字典
    """
    # 计算偏移量
    offset = (page - 1) * limit
    
    # 构建基本查询，直接从runs表获取指标（不再从metrics表查询）
    base_sql = """
    SELECT 
        r.run_id, 
        r.strategy, 
        r.code, 
        r.start_time, 
        r.end_time, 
        r.initial_capital, 
        r.final_capital, 
        r.created_at,
        
        -- 直接从runs表获取指标
        r.max_drawdown, 
        r.sharpe,
        r.win_rate, 
        r.trade_count, 
        r.total_fee, 
        r.total_profit
    
    FROM runs r
    """
    
    # 构建过滤条件
    filters = []
    params = {'limit': limit, 'offset': offset}
    
    if code:
        filters.append("r.code = :code")
        params['code'] = code
    
    if strategy:
        filters.append("r.strategy = :strategy")
        params['strategy'] = strategy
    
    # 构建排序子句
    order_by = "ORDER BY r.created_at DESC"  # 默认排序
    
    # 定义前端字段名到后端字段名的映射
    field_mapping = {
        'totalReturn': None,  # 总收益率是计算字段，需要特殊处理
        'maxDrawdown': 'max_drawdown',
        'sharpe': 'sharpe',
        'strategy': 'r.strategy',
        'code': 'r.code',
        'created_at': 'r.created_at',
        'win_rate': 'r.win_rate',
        'trade_count': 'r.trade_count',
        'total_fee': 'r.total_fee',
        'total_profit': 'r.total_profit'
    }
    
    # 处理排序参数
    if sortField and sortField in field_mapping:
        backend_field = field_mapping[sortField]
        # 对于总收益率这种计算字段，我们需要特殊处理
        if sortField == 'totalReturn':
            order_by = f"ORDER BY ((r.final_capital - r.initial_capital) / r.initial_capital) {sortOrder == 'ascend' and 'ASC' or 'DESC'}"
        elif backend_field:
            order_by = f"ORDER BY {backend_field} {sortOrder == 'ascend' and 'ASC' or 'DESC'}"
    
    # 构建完整查询
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    sql = f"{base_sql} {where_clause} {order_by} LIMIT :limit OFFSET :offset"
    
    # 查询记录
    df = fetch_df(sql, **params)
    
    # 查询总数
    count_sql = f"SELECT COUNT(*) as total FROM runs r {where_clause}"
    count_df = fetch_df(count_sql, **{k: v for k, v in params.items() if k not in ['limit', 'offset']})
    total = count_df.iloc[0]['total'] if not count_df.empty else 0
    
    # 处理数据确保可JSON序列化
    if not df.empty:
        # 转换datetime类型为字符串
        for col in ['start_time', 'end_time', 'created_at']:
            if col in df.columns:
                # 转换datetime64类型为字符串
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                # 处理None值
                df[col] = df[col].fillna('')
        
        # 确保所有指标字段存在且为数值类型
        for col in ['max_drawdown', 'sharpe', 'win_rate', 'trade_count', 'total_fee', 'total_profit']:
            if col in df.columns:
                # 转换为float类型，处理None值
                # 先填充空值，再进行类型推断，最后转换为浮点数以避免Pandas FutureWarning
                df[col] = df[col].fillna(0).infer_objects(copy=False).astype(float)
        
        # 转换其他数值类型确保可序列化
        for col in df.select_dtypes(include=['number']).columns:
            # 将numpy数值类型转换为Python原生类型
            df[col] = df[col].apply(lambda x: x.item() if isinstance(x, (np.integer, np.floating)) else x)
            # 处理NaN值
            df[col] = df[col].fillna(0)
    
    return {
        'rows': df,
        'total': total
    }

import logging
import datetime
import json

logger = logging.getLogger(__name__)

def run_detail(run_id: str):
    
    # 获取基本回测信息，包含新增的paras字段和所有指标
    df_run = fetch_df("""SELECT run_id, strategy, code, start_time, end_time, interval, initial_capital, final_capital, created_at, paras, max_drawdown, sharpe, win_rate, trade_count, total_fee, total_profit
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
            "interval": "1m",
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
    df_m = fetch_df("""SELECT metric_name, metric_value FROM metrics WHERE run_id=:rid""", rid=run_id)

    # 从runs表获取主要指标并添加到metrics列表中（如果metrics表中不存在）
    if not df_run.empty:
        run_data = df_run.iloc[0]
        
        # 检查并添加sharpe指标
        if 'sharpe' in run_data and pd.notna(run_data['sharpe']) and not any(df_m['metric_name'] == 'sharpe'):
            sharpe_row = pd.DataFrame([{'metric_name': 'sharpe', 'metric_value': float(run_data['sharpe'])}])
            df_m = pd.concat([df_m, sharpe_row], ignore_index=True)
            
        # 检查并添加max_drawdown指标
        if 'max_drawdown' in run_data and pd.notna(run_data['max_drawdown']) and not any(df_m['metric_name'] == 'max_drawdown'):
            max_drawdown_row = pd.DataFrame([{'metric_name': 'max_drawdown', 'metric_value': float(run_data['max_drawdown'])}])
            df_m = pd.concat([df_m, max_drawdown_row], ignore_index=True)
            
        # 检查并添加final_return指标
        if 'final_capital' in run_data and 'initial_capital' in run_data and pd.notna(run_data['final_capital']) and pd.notna(run_data['initial_capital']) and run_data['initial_capital'] > 0 and not any(df_m['metric_name'] == 'final_return'):
            final_return = float(run_data['final_capital']) / float(run_data['initial_capital']) - 1
            final_return_row = pd.DataFrame([{'metric_name': 'final_return', 'metric_value': final_return}])
            df_m = pd.concat([df_m, final_return_row], ignore_index=True)
            
        # 检查并添加win_rate指标
        if 'win_rate' in run_data and pd.notna(run_data['win_rate']) and not any(df_m['metric_name'] == 'win_rate'):
            win_rate_row = pd.DataFrame([{'metric_name': 'win_rate', 'metric_value': float(run_data['win_rate'])}])
            df_m = pd.concat([df_m, win_rate_row], ignore_index=True)
            
        # 检查并添加trade_count指标
        if 'trade_count' in run_data and pd.notna(run_data['trade_count']) and not any(df_m['metric_name'] == 'trade_count'):
            trade_count_row = pd.DataFrame([{'metric_name': 'trade_count', 'metric_value': float(run_data['trade_count'])}])
            df_m = pd.concat([df_m, trade_count_row], ignore_index=True)
            
        # 检查并添加total_fee指标
        if 'total_fee' in run_data and pd.notna(run_data['total_fee']) and not any(df_m['metric_name'] == 'total_fee'):
            total_fee_row = pd.DataFrame([{'metric_name': 'total_fee', 'metric_value': float(run_data['total_fee'])}])
            df_m = pd.concat([df_m, total_fee_row], ignore_index=True)
            
        # 检查并添加total_profit指标
        if 'total_profit' in run_data and pd.notna(run_data['total_profit']) and not any(df_m['metric_name'] == 'total_profit'):
            total_profit_row = pd.DataFrame([{'metric_name': 'total_profit', 'metric_value': float(run_data['total_profit'])}])
            df_m = pd.concat([df_m, total_profit_row], ignore_index=True)
    # 从整合后的trades表中读取equity相关数据
    # 注意：我们现在从trades表中获取nav和drawdown数据，而不是从equity_curve表
    df_e = fetch_df("""
        SELECT datetime, nav, drawdown 
        FROM trades 
        WHERE run_id=:rid 
        ORDER BY datetime
    """, rid=run_id)
    
    # 如果trades表中没有equity数据（比如没有交易的情况），我们需要处理这种边缘情况
    if df_e.empty:
        # 创建一个最小的equity数据集，避免前端显示为空
        # 这里可以考虑从runs表获取初始和结束时间，创建一些基本的equity数据点
        df_e = pd.DataFrame({
            'datetime': [pd.Timestamp.now()],
            'nav': [0],
            'drawdown': [0]
        })
    
    # 获取交易记录数据，包括整合后的字段
    df_t = fetch_df("""
        SELECT run_id, datetime, code, side, trade_type, price, qty, amount, fee, 
               realized_pnl, nav, drawdown, avg_price, current_qty, current_avg_price, close_price, current_cash
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
