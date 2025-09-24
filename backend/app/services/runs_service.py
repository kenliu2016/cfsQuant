
import pandas as pd
import numpy as np
from ..common import LoggerFactory
import datetime
import json

# 使用LoggerFactory替换原有logger
logger = LoggerFactory.get_logger('runs_service')

# 避免Pandas future downcasting警告
pd.set_option('future.no_silent_downcasting', True)
from ..db import fetch_df, execute

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

def get_grid_levels(run_id: str) -> list:
    """
    获取特定回测ID的网格级别数据
    
    Args:
        run_id: 回测ID
        
    Returns:
        网格级别数据列表
    """
    # 查询grid_levels表获取指定run_id的网格级别数据
    df_grid = fetch_df("""
        SELECT run_id, level, price, name 
        FROM grid_levels 
        WHERE run_id = :rid
        ORDER BY level
    """, rid=run_id)
    
    # 处理查询结果
    if df_grid.empty:
        # 如果没有找到数据，返回空列表
        logger.debug(f"未找到run_id为{run_id}的网格级别数据")
        return []
    
    # 确保返回的数据是可JSON序列化的
    grid_levels = df_grid.to_dict(orient="records")
    
    # 处理price字段，确保是float类型
    for level in grid_levels:
        if 'price' in level:
            try:
                level['price'] = float(level['price'])
            except (ValueError, TypeError):
                level['price'] = 0.0
        
    logger.debug(f"成功获取网格级别数据，run_id: {run_id}, 级别数量: {len(grid_levels)}")
    return grid_levels

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
            "trades": [],
            "grid_levels": [],
            "klines": []
        }
    
    # 获取指标数据
    df_m = fetch_df("""SELECT metric_name, metric_value FROM metrics WHERE run_id=:rid""", rid=run_id)

    # 从runs表获取主要指标并添加到metrics列表中（如果metrics表中不存在）
    if not df_run.empty:
        run_data = df_run.iloc[0]
        
        # 检查并添加sharpe指标
        if 'sharpe' in run_data and pd.notna(run_data['sharpe']) and not any(df_m['metric_name'] == 'sharpe'):
            sharpe_row = pd.DataFrame([{'metric_name': 'sharpe', 'metric_value': float(run_data['sharpe'])}])
            # 避免FutureWarning：在concat前检查df_m是否为空
            if df_m.empty:
                df_m = sharpe_row
            else:
                df_m = pd.concat([df_m, sharpe_row], ignore_index=True)
            
        # 检查并添加max_drawdown指标
        if 'max_drawdown' in run_data and pd.notna(run_data['max_drawdown']) and not any(df_m['metric_name'] == 'max_drawdown'):
            max_drawdown_row = pd.DataFrame([{'metric_name': 'max_drawdown', 'metric_value': float(run_data['max_drawdown'])}])
            # 避免FutureWarning：在concat前检查df_m是否为空
            if df_m.empty:
                df_m = max_drawdown_row
            else:
                df_m = pd.concat([df_m, max_drawdown_row], ignore_index=True)
            
        # 检查并添加final_return指标
        if 'final_capital' in run_data and 'initial_capital' in run_data and pd.notna(run_data['final_capital']) and pd.notna(run_data['initial_capital']) and run_data['initial_capital'] > 0 and not any(df_m['metric_name'] == 'final_return'):
            final_return = float(run_data['final_capital']) / float(run_data['initial_capital']) - 1
            final_return_row = pd.DataFrame([{'metric_name': 'final_return', 'metric_value': final_return}])
            # 避免FutureWarning：在concat前检查df_m是否为空
            if df_m.empty:
                df_m = final_return_row
            else:
                df_m = pd.concat([df_m, final_return_row], ignore_index=True)
            
        # 检查并添加win_rate指标
        if 'win_rate' in run_data and pd.notna(run_data['win_rate']) and not any(df_m['metric_name'] == 'win_rate'):
            win_rate_row = pd.DataFrame([{'metric_name': 'win_rate', 'metric_value': float(run_data['win_rate'])}])
            # 避免FutureWarning：在concat前检查df_m是否为空
            if df_m.empty:
                df_m = win_rate_row
            else:
                df_m = pd.concat([df_m, win_rate_row], ignore_index=True)
            
        # 检查并添加trade_count指标
        if 'trade_count' in run_data and pd.notna(run_data['trade_count']) and not any(df_m['metric_name'] == 'trade_count'):
            trade_count_row = pd.DataFrame([{'metric_name': 'trade_count', 'metric_value': float(run_data['trade_count'])}])
            # 避免FutureWarning：在concat前检查df_m是否为空
            if df_m.empty:
                df_m = trade_count_row
            else:
                df_m = pd.concat([df_m, trade_count_row], ignore_index=True)
            
        # 检查并添加total_fee指标
        if 'total_fee' in run_data and pd.notna(run_data['total_fee']) and not any(df_m['metric_name'] == 'total_fee'):
            total_fee_row = pd.DataFrame([{'metric_name': 'total_fee', 'metric_value': float(run_data['total_fee'])}])
            # 避免FutureWarning：在concat前检查df_m是否为空
            if df_m.empty:
                df_m = total_fee_row
            else:
                df_m = pd.concat([df_m, total_fee_row], ignore_index=True)
            
        # 检查并添加total_profit指标
        if 'total_profit' in run_data and pd.notna(run_data['total_profit']) and not any(df_m['metric_name'] == 'total_profit'):
            total_profit_row = pd.DataFrame([{'metric_name': 'total_profit', 'metric_value': float(run_data['total_profit'])}])
            # 避免FutureWarning：在concat前检查df_m是否为空
            if df_m.empty:
                df_m = total_profit_row
            else:
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
    
    # 获取网格级别数据
    grid_levels = get_grid_levels(run_id)
    
    # 获取K线数据
    klines = []
    try:
        from .market_service import MarketDataService
        market_service = MarketDataService()
        
        # 从run_info中获取所需参数
        code = run_info.get('code', '')
        interval = run_info.get('interval', '1m')
        start_time = run_info.get('start_time', '')
        end_time = run_info.get('end_time', '')
        
        if code and start_time and end_time:
            # 调用市场服务获取K线数据
            df_candles, _ = market_service.get_candles(code, start_time, end_time, interval)
            
            # 确保返回的数据是可JSON序列化的
            if not df_candles.empty:
                # 处理datetime类型
                if 'datetime' in df_candles.columns:
                    df_candles['datetime'] = df_candles['datetime'].astype(str)
                
                # 处理数值列中的特殊值
                numeric_columns = df_candles.select_dtypes(include=['float64', 'int64']).columns
                for col in numeric_columns:
                    df_candles[col] = df_candles[col].fillna(0)
                    df_candles[col] = df_candles[col].replace([float('inf'), float('-inf')], 0)
                    df_candles[col] = df_candles[col].astype(float)
                
                klines = df_candles.to_dict(orient="records")
        logger.debug(f"成功获取K线数据，run_id: {run_id}, 数据点数量: {len(klines)}")
    except Exception as e:
        logger.error(f"获取K线数据失败: {str(e)}")
        klines = []
    
    logger.debug(f"成功获取回测详情，run_id: {run_id}, 策略: {run_info.get('strategy', '未知')}")
    
    # 统一返回数据：基本信息、指标数据、equity数据、交易数据、网格级别数据和K线数据
    return {
        "info": run_info,
        "metrics": df_m.to_dict(orient="records"),
        "equity": df_e.to_dict(orient="records"),
        "trades": df_t.to_dict(orient="records"),
        "grid_levels": grid_levels,
        "klines": klines
    }

def delete_run(run_id: str) -> bool:
    """
    删除指定的run记录及其关联数据
    
    Args:
        run_id: 要删除的回测ID
        
    Returns:
        bool: 是否删除成功
    """
    try:
        logger.info(f"开始删除回测记录，run_id: {run_id}")
        
        # 开启事务执行删除操作
        # 首先删除关联的子表数据
        # 删除trades表中的关联数据
        execute("DELETE FROM trades WHERE run_id = :rid", rid=run_id)
        logger.debug(f"已删除trades表中关联数据，run_id: {run_id}")
        
        # 删除metrics表中的关联数据
        execute("DELETE FROM metrics WHERE run_id = :rid", rid=run_id)
        logger.debug(f"已删除metrics表中关联数据，run_id: {run_id}")
        
        # 删除equity_curve表中的关联数据
        execute("DELETE FROM equity_curve WHERE run_id = :rid", rid=run_id)
        logger.debug(f"已删除equity_curve表中关联数据，run_id: {run_id}")
        
        # 删除grid_levels表中的关联数据
        execute("DELETE FROM grid_levels WHERE run_id = :rid", rid=run_id)
        logger.debug(f"已删除grid_levels表中关联数据，run_id: {run_id}")
        
        # 最后删除positions表中的关联数据
        execute("DELETE FROM positions WHERE run_id = :rid", rid=run_id)
        logger.debug(f"已删除positions表中关联数据，run_id: {run_id}")
        
        # 最后删除runs表中的主记录
        result = execute("DELETE FROM runs WHERE run_id = :rid", rid=run_id)
        logger.debug(f"已删除runs表中主记录，run_id: {run_id}")
        
        logger.info(f"回测记录删除成功，run_id: {run_id}")
        return True
        
    except Exception as e:
        logger.error(f"删除回测记录失败，run_id: {run_id}, 错误: {str(e)}")
        raise

def batch_delete_runs(run_ids: list) -> dict:
    """
    批量删除多个回测记录及其关联数据
    
    Args:
        run_ids: 要删除的回测ID列表
        
    Returns:
        dict: 包含删除结果的字典，记录成功和失败的数量
    """
    success_count = 0
    failed_count = 0
    failed_ids = []
    
    logger.info(f"开始批量删除回测记录，共 {len(run_ids)} 条")
    
    for run_id in run_ids:
        try:
            delete_run(run_id)
            success_count += 1
        except Exception as e:
            logger.error(f"批量删除回测记录失败，run_id: {run_id}, 错误: {str(e)}")
            failed_count += 1
            failed_ids.append(run_id)
    
    logger.info(f"批量删除回测记录完成，成功: {success_count} 条，失败: {failed_count} 条")
    
    return {
        "success": success_count,
        "failed": failed_count,
        "failed_ids": failed_ids
    }
