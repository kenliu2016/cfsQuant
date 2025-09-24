import threading, uuid, itertools, time, json
import uuid
import itertools
import time
import json
import logging
import inspect
from typing import Dict, Any, Optional, List
import pandas as pd
from ..services.backtest_service import run_backtest
from ..db import fetch_df, to_sql, execute
from sqlalchemy import text
from ..celery_config import celery_app

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 日志配置已完成

@celery_app.task(bind=True, name='app.services.tuning_service.run_parameter_tuning', queue='tuning')
def run_parameter_tuning(self, task_id: str, strategy: str, code: str, start: str, end: str, params_grid: Dict[str, list], interval: str = '1m', total: int = 1):
    """
    运行参数调优任务
    
    Args:
        self: Celery任务实例
        task_id: 任务ID
        strategy: 策略名称
        code: 交易对代码
        start: 开始时间
        end: 结束时间
        params_grid: 参数网格
        interval: K线周期
        total: 总任务数
        
    Returns:
        Dict: 调优结果
    """
    try:
        # 任务开始执行
        
        # 获取当前时间，用于设置start_time和timeout
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 尝试使用不同的调用方式
        try:
            # 方法1: 原始调用方式
            execute("UPDATE tuning_tasks SET status = :status, start_time = :start_time, timeout = (NOW() + INTERVAL '12 hours') WHERE task_id = :task_id", task_id=task_id, status='running', start_time=current_time)
        except Exception as e:
            try:
                # 方法2: 使用字典传递参数
                params = {"task_id": task_id, "status": "running", "start_time": current_time}
                execute("UPDATE tuning_tasks SET status = :status, start_time = :start_time, timeout = (NOW() + INTERVAL '12 hours') WHERE task_id = :task_id", **params)
            except Exception as e2:
                try:
                    # 方法3: 直接使用SQL字符串，不使用参数绑定
                    sql = f"UPDATE tuning_tasks SET status = 'running', start_time = '{current_time}', timeout = (NOW() + INTERVAL '12 hours') WHERE task_id = '{task_id}'"
                    execute(sql)
                    logger.info("方法3调用成功！")
                except Exception as e3:
                    logger.error(f"方法3调用失败: {e3}")
                    # 如果所有方法都失败，使用原始的execute_async函数
                    from ..db import execute_async
                    import asyncio
                    asyncio.run(execute_async("UPDATE tuning_tasks SET status = :status, start_time = :start_time, timeout = (NOW() + INTERVAL '12 hours') WHERE task_id = :task_id", task_id=task_id, status='running', start_time=current_time))
        
        from ..services.market_service import get_candles
        
        keys = list(params_grid.keys()) if params_grid else []
        grids = [params_grid[k] for k in keys] if params_grid else []
        
        # 获取K线数据
        candles_result = get_candles(code, start, end, interval)
        # 根据返回值类型确定如何获取DataFrame
        if isinstance(candles_result, tuple):
            # 如果是元组，根据长度决定是两个值还是三个值的情况
            if len(candles_result) == 3:
                df, _, _ = candles_result
            else:
                df, _ = candles_result
        else:
            # 否则直接使用
            df = candles_result
        
        finished = 0
        runs = []
        
        # 遍历所有参数组合
        for vals in itertools.product(*grids) if keys else [()]:
            p = {k:v for k,v in zip(keys, vals)} if keys else {}
            # 构建完整的参数对象，包含interval
            full_params = {
                'code': code,
                'start': start,
                'end': end,
                'interval': interval,
                **p
            }
            
            # 调用run_backtest函数，传入正确的参数
            backtest_result = run_backtest(df, full_params, strategy)
            
            # 确保run_id是字符串类型
            run_id = str(backtest_result.get('run_id'))
            runs.append({'params': p, 'run_id': run_id})
            finished += 1
            
            # 获取参数组合的完成时间
            completion_time = time.strftime('%Y-%m-%d %H:%M:%S')
            
            # 将回测结果记录到tuning_results表中
            try:
                # 首先检查run_id是否存在于runs表中
                # 这个检查是为了避免外键约束错误
                run_exists_query = "SELECT 1 FROM runs WHERE run_id = :run_id LIMIT 1"
                run_exists_result = fetch_df(run_exists_query, **{"run_id": run_id})
                
                if run_exists_result.empty:
                    logger.warning(f"Run ID {run_id} does not exist in runs table, skipping tuning_results insertion")
                else:
                    # 确保所有数据都是Python原生类型且可JSON序列化
                    def make_serializable(value):
                        """将值转换为可JSON序列化的类型"""
                        if isinstance(value, (int, float, str, bool, type(None))):
                            return value
                        elif isinstance(value, list):
                            return [make_serializable(item) for item in value]
                        elif isinstance(value, dict):
                            return {k: make_serializable(v) for k, v in value.items()}
                        else:
                            return str(value)  # 对于其他类型，转换为字符串
                    
                    serializable_params = make_serializable(p)
                    
                    result_data = {
                        'task_id': task_id,
                        'run_id': run_id,
                        'params': serializable_params,  # 存储可序列化的参数字典
                        'created_at': completion_time
                    }
                    result_df = pd.DataFrame([result_data])
                    to_sql(result_df, 'tuning_results')
            except Exception as e:
                logger.error(f"Error creating tuning result record: {e}")
            
            # 更新tuning_tasks表中的进度
            try:
                execute("UPDATE tuning_tasks SET finished = :finished WHERE task_id = :task_id", task_id=task_id, finished=finished)
            except Exception as e:
                pass
            
            # 更新Celery任务状态 - 将数值转换为Python原生int类型以支持JSON序列化
            self.update_state(state='PROGRESS', meta={'finished': int(finished), 'total': int(total)})
        
        # 更新任务状态为完成
        try:
            execute("UPDATE tuning_tasks SET status = :status WHERE task_id = :task_id", task_id=task_id, status='finished')
        except Exception as e:
            pass
        
        return {
            'task_id': task_id,
            'status': 'finished',
            'finished': int(finished),
            'total': int(total),
            'runs': runs
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # 更新任务状态为错误
        try:
            execute("UPDATE tuning_tasks SET status = :status, error = :error WHERE task_id = :task_id", task_id=task_id, status='error', error=error_msg)
        except Exception as db_error:
            pass
        
        # 重新抛出异常，让Celery记录错误
        raise

def start_tuning_async(strategy: str, code: str, start: str, end: str, params_grid: Dict[str, list], interval: str = '1m') -> str:
    """
    异步启动参数调优任务
    
    Args:
        strategy: 策略名称
        code: 交易对代码
        start: 开始时间
        end: 结束时间
        params_grid: 参数网格
        interval: K线周期
        
    Returns:
        str: 任务ID
    """
    task_id = str(uuid.uuid4())
    
    # 计算总任务数
    total = 1
    if params_grid:
        keys = list(params_grid.keys())
        grids = [params_grid[k] for k in keys]
        total = 0
        for _ in itertools.product(*grids):
            total += 1
    
    # 在tuning_tasks表中创建记录
    try:
        task_data = {
            'task_id': task_id,
            'strategy': strategy,
            'status': 'pending',
            'total': total,
            'finished': 0,
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        task_df = pd.DataFrame([task_data])
        to_sql(task_df, 'tuning_tasks')
    except Exception as e:
        raise
    
    # 使用Celery提交异步任务
    try:
        # 注意：这里传递total作为额外参数，以便在任务中访问
        run_parameter_tuning.delay(task_id, strategy, code, start, end, params_grid, interval, total)
    except Exception as e:
        # 如果提交失败，更新任务状态为错误
        try:
            execute("UPDATE tuning_tasks SET status = :status, error = :error WHERE task_id = :task_id", task_id=task_id, status='error', error=str(e))
        except Exception as db_error:
            raise
    
    return task_id

def get_all_tuning_tasks() -> List[Dict[str, Any]]:
    """
    获取所有参数调优任务
    
    Returns:
        List[Dict]: 所有任务的状态信息列表
    """
    try:
        # 从数据库获取所有任务状态
        query = "SELECT task_id, strategy, status, total, finished, start_time, created_at, error FROM tuning_tasks ORDER BY created_at DESC"
        result = fetch_df(query)
        
        if result.empty:
            return []
        
        tasks = []
        for _, row in result.iterrows():
            task_info = {
                'task_id': row['task_id'],
                'strategy': row['strategy'],
                'status': row['status'],
                'total': int(row['total']),
                'finished': int(row['finished']),
                'start_time': str(row['start_time']) if pd.notna(row['start_time']) else None,
                'created_at': str(row['created_at']),
                'error': row['error'] if pd.notna(row['error']) else None
            }
            tasks.append(task_info)
        
        # 按状态排序：未开始(pending) -> 进行中(running) -> 已完成(finished) -> 出错(error)
        status_order = {'pending': 0, 'running': 1, 'finished': 2, 'error': 3}
        tasks.sort(key=lambda x: (status_order.get(x['status'], 999), x['created_at']), reverse=False)
        
        return tasks
    except Exception as e:
        return []

def get_tuning_status(task_id: str, page: Optional[int] = None, page_size: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    获取参数调优任务状态
    
    Args:
        task_id: 任务ID
        page: 页码，从1开始
        page_size: 每页记录数
        
    Returns:
        Dict: 任务状态信息，或None如果任务不存在
    """
    try:
        # 从数据库获取任务状态，包括新增的start_time、timeout和error字段
        # 使用安全的方式查询，处理error列可能不存在的情况
        try:
            # 尝试包含error列的查询
            query = "SELECT status, total, finished, start_time, timeout, error FROM tuning_tasks WHERE task_id = :task_id"
            result = fetch_df(query, **{"task_id": task_id})
        except Exception as e:
            # 如果出错，回退到不包含error列的查询
            query = "SELECT status, total, finished, start_time, timeout FROM tuning_tasks WHERE task_id = :task_id"
            result = fetch_df(query, **{"task_id": task_id})
        
        if result.empty:
            # 添加任务ID频率检查，避免频繁警告
            import time
            import logging
            logger = logging.getLogger(__name__)
            if not hasattr(get_tuning_status, 'last_warned'):
                get_tuning_status.last_warned = {}
            current_time = time.time()
            if task_id not in get_tuning_status.last_warned or current_time - get_tuning_status.last_warned[task_id] > 60:
                logger.warning(f"Tuning task not found: {task_id}")
                get_tuning_status.last_warned[task_id] = current_time
            return None
        
        # 从Celery获取任务状态（如果任务正在运行）
        task_status = None
        if result.iloc[0]['status'] == 'running':
            try:
                task = run_parameter_tuning.AsyncResult(task_id)
                if task.state == 'PROGRESS' and task.info:
                    task_status = task.info
            except Exception as e:
                pass
        
        # 构建返回结果 - 将numpy.int64类型转换为Python原生int类型以支持JSON序列化
        # 确保处理可能为None的字段
        
        # 获取runs总数的查询
        runs_count_query = """SELECT COUNT(*) as count 
                           FROM tuning_results t 
                           WHERE t.task_id = :task_id"""
        runs_count_result = fetch_df(runs_count_query, **{"task_id": task_id})
        runs_total_count = int(runs_count_result['count'].iloc[0]) if not runs_count_result.empty else 0
        
        # 从数据库查询runs信息，支持分页
        runs_query = """SELECT t.run_id, t.params, t.created_at, 
                               r.trade_count, r.win_rate, r.final_return, 
                               r.sharpe, r.max_drawdown 
                        FROM tuning_results t 
                        LEFT JOIN runs r ON t.run_id = r.run_id 
                        WHERE t.task_id = :task_id 
                        ORDER BY t.created_at DESC"""
        
        # 添加分页逻辑
        if page is not None and page_size is not None:
            offset = (page - 1) * page_size
            runs_query += " LIMIT :limit OFFSET :offset"
            runs_result = fetch_df(runs_query, **{"task_id": task_id, "limit": page_size, "offset": offset})
        else:
            runs_result = fetch_df(runs_query, **{"task_id": task_id})
        
        runs = []
        if not runs_result.empty:
            for _, row in runs_result.iterrows():
                run_info = {
                    'run_id': row['run_id'],
                    'params': row['params'] if pd.notna(row['params']) else {},
                    'created_at': str(row['created_at']) if pd.notna(row['created_at']) else None,
                    'trade_count': int(row['trade_count']) if pd.notna(row['trade_count']) else 0,
                    'win_rate': float(row['win_rate']) if pd.notna(row['win_rate']) else 0.0,
                    'final_return': float(row['final_return']) if pd.notna(row['final_return']) else 0.0,
                    'sharpe': float(row['sharpe']) if pd.notna(row['sharpe']) else 0.0,
                    'max_drawdown': float(row['max_drawdown']) if pd.notna(row['max_drawdown']) else 0.0
                }
                runs.append(run_info)
        
        status_info = {
            'task_id': task_id,
            'status': result.iloc[0]['status'],
            'total': int(result.iloc[0]['total']),
            'finished': int(result.iloc[0]['finished']),
            'start_time': str(result.iloc[0]['start_time']) if pd.notna(result.iloc[0]['start_time']) else None,
            'timeout': str(result.iloc[0]['timeout']) if pd.notna(result.iloc[0]['timeout']) else None,
            'error': result.iloc[0]['error'] if 'error' in result.columns and pd.notna(result.iloc[0]['error']) else None,
            'runs': runs,  # 返回实际的已完成组合数据
            'runs_total_count': runs_total_count,
            'page': page,
            'page_size': page_size
        }
        
        # 移除调试日志，避免不必要的日志输出
        
        # 如果有Celery任务状态信息，合并它
        if task_status:
            status_info.update(task_status)
        
        return status_info
        
    except Exception as e:
        logger.error(f"获取调优任务状态失败: {e}")
        return None
