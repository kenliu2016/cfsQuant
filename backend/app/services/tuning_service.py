import threading
import uuid
import itertools
import time
import json
import logging
from datetime import datetime
import traceback  # 添加traceback导入

# 创建logger实例
logger = logging.getLogger('tuning_service')
logger.setLevel(logging.INFO)
import inspect
from typing import Dict, Any, Optional, List
import pandas as pd
import sqlalchemy
from .backtest_service import run_backtest
from .market_service import MarketDataService
from .runs_service import delete_run
from ..db import fetch_df, to_sql, execute
from ..celery_config import celery_app

# 使用Python内置logging模块
logger.info('tuning_service logger initialized')

# 日志配置已完成

# 全局变量：启用内存优化模式
enable_memory_optimization = True

@celery_app.task(bind=True, name='app.services.tuning_service.run_parameter_tuning', queue='tuning')
def run_parameter_tuning(self, task_id: str, strategy: str, code: str, start_time: str, end_time: str, params_grid: Dict[str, list], interval: str = '1m', total: int = 1):
    """
    运行参数调优任务
    
    Args:
        self: Celery任务实例
        task_id: 任务ID
        strategy: 策略名称
        code: 交易对代码
        start_time: 开始时间
        end_time: 结束时间
        params_grid: 参数网格
        interval: K线周期
        total: 总任务数
        
    Returns:
        Dict: 调优结果
    """
    logger.info(f"开始执行调优任务: task_id={task_id}, strategy={strategy}, code={code}")
    
    # 初始化计数器和结果列表
    completed = 0
    results = []
    failed_runs = 0
    max_failures = 5  # 设置最大失败次数限制
    
    try:
        # 任务开始执行
        
        # 获取当前时间，用于设置start_time和timeout
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 尝试使用不同的调用方式
        try:
            # 方法1: 原始调用方式
            execute("UPDATE tuning_tasks SET status = :status, start_time = :start_time, timeout = (NOW() + INTERVAL '12 hours') WHERE task_id = :task_id", task_id=task_id, status='running', start_time=current_time)
            logger.info(f"任务{task_id}状态已更新为running")
        except Exception as e:
            logger.warning(f"更新任务状态失败（方法1）: {str(e)}")
            try:
                # 方法2: 使用字典传递参数
                params = {"task_id": task_id, "status": "running", "start_time": current_time}
                execute("UPDATE tuning_tasks SET status = :status, start_time = :start_time, timeout = (NOW() + INTERVAL '12 hours') WHERE task_id = :task_id", **params)
                logger.info(f"任务{task_id}状态已更新为running（方法2）")
            except Exception as e2:
                logger.warning(f"更新任务状态失败（方法2）: {str(e2)}")
                try:
                    # 方法3: 直接使用SQL字符串，不使用参数绑定
                    sql = f"UPDATE tuning_tasks SET status = 'running', start_time = '{current_time}', timeout = (NOW() + INTERVAL '12 hours') WHERE task_id = '{task_id}'"
                    execute(sql)
                    logger.info(f"任务{task_id}状态已更新为running（方法3）")
                except Exception as e3:
                    logger.error(f"更新任务状态失败（方法3）: {str(e3)}")
                    try:
                        # 如果所有方法都失败，使用原始的execute_async函数
                        from ..db import execute_async
                        import asyncio
                        asyncio.run(execute_async("UPDATE tuning_tasks SET status = :status, start_time = :start_time, timeout = (NOW() + INTERVAL '12 hours') WHERE task_id = :task_id", task_id=task_id, status='running', start_time=current_time))
                    except Exception as e4:
                        logger.error(f"使用execute_async更新状态失败: {str(e4)}")
        
        from ..services.market_service import get_candles
        
        keys = list(params_grid.keys()) if params_grid else []
        # 确保每个参数值都是可迭代的列表
        grids = []
        if params_grid:
            for k in keys:
                value = params_grid[k]
                # 如果不是列表，转换为单元素列表
                if not isinstance(value, list):
                    grids.append([value])
                else:
                    grids.append(value)
        
        # 获取K线数据 - 注意get_candles是MarketDataService类的方法
        # 我们需要先实例化服务类
        from .market_service import MarketDataService
        market_service = MarketDataService()
        candles_result = market_service.get_candles(code, start_time, end_time, interval)
        
        # 检查candles_result是否为空或None
        if candles_result is None:
            raise ValueError("get_candles返回值为None")
        
        # 检查candles_result是否为元组
        if not isinstance(candles_result, tuple):
            raise ValueError(f"get_candles返回的不是有效的元组，而是: {type(candles_result)}")
        
        # 检查元组是否至少有一个元素
        if len(candles_result) == 0:
            raise ValueError("get_candles返回的元组为空")
        
        # 从元组中提取DataFrame（第一个元素）
        df = candles_result[0]
        
        # 验证df是否为DataFrame
        if not isinstance(df, pd.DataFrame):
            raise ValueError(f"从get_candles返回值中提取的不是DataFrame，类型为: {type(df)}")
        
        # 检查DataFrame是否为空
        if df.empty:
            raise ValueError(f"获取的K线数据为空，交易对代码: {code}")
        
        # 内存优化：只保留必要的列
        if enable_memory_optimization and not df.empty:
            required_columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
            # 只保留存在的必要列
            available_columns = [col for col in required_columns if col in df.columns]
            df = df[available_columns].copy()
            # 使用更高效的数据类型
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], downcast='float')
        
        finished = 0
        runs = []
        
        # 遍历所有参数组合
        param_combinations = list(itertools.product(*grids)) if keys else [()]
        total_combinations = len(param_combinations)
        
        for vals in param_combinations:
            # 检查失败次数是否超过限制
            if failed_runs >= max_failures:
                logger.error(f"连续失败次数超过限制({max_failures})，任务中断")
                raise Exception(f"连续失败次数超过限制({max_failures})")
                
            try:
                p = {k:v for k,v in zip(keys, vals)} if keys else {}
                # 构建完整的参数对象，包含interval
                full_params = {
                    'code': code,
                    'start': start_time,
                    'end': end_time,
                    'interval': interval,
                    **p
                }
                
                # 调用run_backtest函数，传入正确的参数
                backtest_result = None
                try:
                    backtest_result = run_backtest(df, full_params, strategy)
                    failed_runs = 0  # 重置失败计数
                except Exception as bt_error:
                    failed_runs += 1
                    logger.error(f"回测执行失败: {str(bt_error)}, 当前失败计数: {failed_runs}")
                    # 继续处理下一个参数组合
                    continue
                
                # 安全获取run_id，确保即使backtest_result为None或不包含run_id键也能正常工作
                run_id = backtest_result.get('run_id', 'unknown') if backtest_result else 'unknown'
                # 确保run_id是字符串类型
                run_id = str(run_id)
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
                    
                    if not run_exists_result.empty:
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
                        
                        # 将参数转换为JSON字符串后再存储到数据库
                        params_json = json.dumps(serializable_params)
                        
                        # 验证JSON字符串的有效性
                        try:
                            parsed_json = json.loads(params_json)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON验证失败: {e}")
                            params_json = '{}'  # 使用空JSON作为后备
                        
                        result_data = {
                            'task_id': task_id,
                            'run_id': run_id,
                            'params': params_json,  # 存储为JSON字符串
                            'created_at': completion_time
                        }
                        
                        # 使用更高效的方式插入数据
                        try:
                            execute(
                                "INSERT INTO tuning_results (task_id, run_id, params, created_at) VALUES (:task_id, :run_id, :params, :created_at)",
                                **result_data
                            )
                        except Exception as sql_error:
                            logger.error(f"插入tuning_results失败: {str(sql_error)}")
                            # 使用pandas的to_sql作为后备方案
                            try:
                                result_df = pd.DataFrame([result_data])
                                to_sql(result_df, 'tuning_results')
                            except Exception as df_error:
                                logger.error(f"使用DataFrame插入tuning_results也失败: {str(df_error)}")
                except Exception as e:
                    logger.error(f"创建调优结果记录失败: {str(e)}")
                
                # 更新tuning_tasks表中的进度
                try:
                    execute("UPDATE tuning_tasks SET finished = :finished WHERE task_id = :task_id", task_id=task_id, finished=finished)
                except Exception as e:
                    pass
                
                # 更新Celery任务状态 - 将数值转换为Python原生int类型以支持JSON序列化
                self.update_state(state='PROGRESS', meta={'finished': int(finished), 'total': int(total_combinations)})
                
                # 内存优化：定期清理不再需要的变量
                if enable_memory_optimization and finished % 10 == 0:
                    import gc
                    gc.collect()
                    
            except Exception as combination_error:
                failed_runs += 1
                logger.error(f"处理参数组合时出错: {str(combination_error)}, 当前失败计数: {failed_runs}")
                # 继续处理下一个参数组合，不中断整个任务
                continue
        
        # 更新任务状态为完成
        try:
            execute("UPDATE tuning_tasks SET status = :status WHERE task_id = :task_id", task_id=task_id, status='finished')
        except Exception as e:
            pass
        
        return {
            'task_id': task_id,
            'status': 'finished',
            'finished': int(finished),
            'total': int(total_combinations),
            'runs': runs
        }
        
    except Exception as e:
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        logger.error(f"调优任务执行失败: {error_msg}\n{traceback_str}")
        
        # 更新任务状态为错误
        try:
            execute("UPDATE tuning_tasks SET status = :status, error = :error WHERE task_id = :task_id", task_id=task_id, status='error', error=error_msg)
        except Exception as db_error:
            pass
        
        # 重新抛出异常，让Celery记录错误
        raise

def start_tuning_async(strategy: str, code: str, params_grid: Dict[str, list], interval: str = '1m', 
                      start: str = None, end: str = None, start_time: str = None, end_time: str = None,
                      params_config: str = None) -> str:
    """
    异步启动参数调优任务
    
    Args:
        strategy: 策略名称
        code: 交易对代码
        params_grid: 参数网格
        interval: K线周期
        start: 开始时间（旧参数名，向后兼容）
        end: 结束时间（旧参数名，向后兼容）
        start_time: 开始时间（新参数名）
        end_time: 结束时间（新参数名）
        params_config: 完整参数配置JSON字符串
        
    Returns:
        str: 任务ID
    """
    task_id = str(uuid.uuid4())
    
    # 处理参数名兼容性，优先使用新参数名
    if start_time is None and start is not None:
        start_time = start
    if end_time is None and end is not None:
        end_time = end
    
    # 确保开始时间和结束时间不为None
    if start_time is None or end_time is None:
        raise ValueError("开始时间和结束时间不能为空")
    
    # 计算总任务数
    total = 1
    if params_grid:
        keys = list(params_grid.keys())
        # 确保每个参数值都是可迭代的列表
        grids = []
        for k in keys:
            value = params_grid[k]
            # 如果不是列表，转换为单元素列表
            if not isinstance(value, list):
                grids.append([value])
            else:
                grids.append(value)
        total = 0
        for _ in itertools.product(*grids):
            total += 1
    
    # 在tuning_tasks表中创建记录
    try:
        # 构建params JSON字符串，包含所有定义了范围的参数
        # 优先使用params_config，如果不存在则使用params_grid
        if params_config:
            params_json = params_config
        else:
            params_json = json.dumps(params_grid) if params_grid else '{}'
        
        task_data = {
            'task_id': task_id,
            'strategy': strategy,
            'status': 'pending',
            'total': total,
            'finished': 0,
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            # 新增字段
            'code': code,
            'interval': interval,
            'start_time': start_time,  # 保存开始时间
            'end_time': end_time,      # 保存结束时间
            'params': params_json  # 保存参数网格的JSON字符串
        }
        task_df = pd.DataFrame([task_data])
        to_sql(task_df, 'tuning_tasks')
    except Exception as e:
        raise
    
    # 使用Celery提交异步任务
    try:
        # 注意：这里传递total作为额外参数，以便在任务中访问
        run_parameter_tuning.delay(task_id, strategy, code, start_time, end_time, params_grid, interval, total)
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
        # 从数据库获取所有任务状态，包括新添加的字段
        query = "SELECT task_id, strategy, status, total, finished, start_time, created_at, error, code, params FROM tuning_tasks ORDER BY created_at DESC"
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
                'error': row['error'] if pd.notna(row['error']) else None,
                # 新增字段
                'code': row['code'] if pd.notna(row['code']) else '',  # 标的代码
                'params': row['params'] if pd.notna(row['params']) else '{}'  # 参数网格JSON字符串
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

def delete_tuning_task(task_id: str) -> bool:
    """
    删除指定的tuning_task记录及其关联数据
    
    Args:
        task_id: 要删除的调优任务ID
        
    Returns:
        bool: 是否删除成功
    """
    try:
        logger.info(f"开始删除调优任务，task_id: {task_id}")
        
        # 首先获取所有关联的run_id
        run_ids_query = "SELECT run_id FROM tuning_results WHERE task_id = :task_id"
        run_ids_df = fetch_df(run_ids_query, task_id=task_id)
        
        # 逐个删除关联的run记录及其子数据
        if not run_ids_df.empty:
            for _, row in run_ids_df.iterrows():
                run_id = row['run_id']
                try:
                    delete_run(run_id)
                    logger.debug(f"已删除调优任务关联的回测记录，task_id: {task_id}, run_id: {run_id}")
                except Exception as e:
                    logger.error(f"删除关联回测记录失败，run_id: {run_id}, 错误: {str(e)}")
                    # 继续删除其他记录，不中断整个过程
                    continue
        
        # 删除tuning_results表中的关联数据
        execute("DELETE FROM tuning_results WHERE task_id = :task_id", task_id=task_id)
        logger.debug(f"已删除tuning_results表中关联数据，task_id: {task_id}")
        
        # 最后删除tuning_tasks表中的主记录
        execute("DELETE FROM tuning_tasks WHERE task_id = :task_id", task_id=task_id)
        logger.debug(f"已删除tuning_tasks表中主记录，task_id: {task_id}")
        
        logger.info(f"调优任务删除成功，task_id: {task_id}")
        return True
        
    except Exception as e:
        logger.error(f"删除调优任务失败，task_id: {task_id}, 错误: {str(e)}")
        raise
