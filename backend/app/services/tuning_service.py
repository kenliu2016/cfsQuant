import threading, uuid, itertools, time, json
import uuid
import itertools
import threading
import time
import json
import logging
from typing import Dict, Any
import pandas as pd
from ..services.backtest_service import run_backtest
from ..db import fetch_df, to_sql, execute
from sqlalchemy import text

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_tasks = {}  # task_id -> status dict

def start_tuning_async(strategy: str, code: str, start: str, end: str, params_grid: Dict[str, list], interval: str = '1m'):
    from ..services.market_service import get_candles
    task_id = str(uuid.uuid4())
    total = 1
    if params_grid:
        keys = list(params_grid.keys())
        grids = [params_grid[k] for k in keys]
        total = 0
        for _ in itertools.product(*grids):
            total += 1
    _tasks[task_id] = {'status':'pending','total':total,'finished':0,'runs':[],'error':None, 'created_at': time.time()}

    # 在tuning_tasks表中创建记录
    try:
        task_data = {
            'task_id': task_id,  # 直接使用UUID作为task_id
            'strategy': strategy,
            'interval': interval,
            'status': 'pending',
            'total': total,
            'finished': 0,
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        task_df = pd.DataFrame([task_data])
        to_sql(task_df, 'tuning_tasks')
        # 保存数据库task_id（UUID字符串）用于后续更新
        _tasks[task_id]['db_id'] = task_id
    except Exception as e:
        print(f"Error creating tuning task record: {e}")

    def worker():
        try:
            db_task_id = _tasks[task_id].get('db_id')
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
                _tasks[task_id]['runs'].append({'params':p, 'run_id': run_id})
                _tasks[task_id]['finished'] += 1
                
                # 将回测结果记录到tuning_results表中
                if db_task_id and run_id:
                    try:
                        # 确保所有数据都是Python原生类型
                        result_data = {
                            'task_id': db_task_id,  # 直接使用字符串类型的task_id
                            'run_id': run_id,
                            'params': json.dumps(p),
                            'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                        result_df = pd.DataFrame([result_data])
                        to_sql(result_df, 'tuning_results')
                    except Exception as e:
                        print(f"Error creating tuning result record: {e}")
                        
                # 更新tuning_tasks表中的状态
                if db_task_id:
                    try:
                        # 使用参数化查询避免SQL注入
                        execute(text("UPDATE tuning_tasks SET finished = :finished WHERE task_id = :task_id").bindparams(
                            finished=_tasks[task_id]['finished'], 
                            task_id=db_task_id
                        ))
                        logger.info(f"Tuning task {db_task_id} progress: {_tasks[task_id]['finished']}/{_tasks[task_id]['total']} runs completed")
                    except Exception as e:
                        print(f"Error updating tuning task status: {e}")
                        
            _tasks[task_id]['status'] = 'finished'
            
            # 验证finished和total字段是否相等
            if _tasks[task_id]['finished'] == _tasks[task_id]['total']:
                logger.info(f"Tuning task {db_task_id} completed successfully: {_tasks[task_id]['finished']}/{_tasks[task_id]['total']} runs")
            else:
                logger.warning(f"Tuning task {db_task_id} finished with mismatch: {_tasks[task_id]['finished']}/{_tasks[task_id]['total']} runs")
            
            # 更新最终状态
            if db_task_id:
                try:
                    # 使用参数化查询避免SQL注入
                    execute(text("UPDATE tuning_tasks SET status = :status WHERE task_id = :task_id").bindparams(
                        status='finished', 
                        task_id=db_task_id
                    ))
                except Exception as e:
                    print(f"Error updating tuning task status: {e}")
        except Exception as e:
            _tasks[task_id]['status'] = 'error'
            _tasks[task_id]['error'] = str(e)
            # 更新错误状态
            db_task_id = _tasks[task_id].get('db_id')
            if db_task_id:
                try:
                    # 使用参数化查询避免SQL注入
                    execute(text("UPDATE tuning_tasks SET status = :status WHERE task_id = :task_id").bindparams(
                        status='error', 
                        task_id=db_task_id
                    ))
                except Exception as e:
                    print(f"Error updating tuning task status: {e}")

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    return task_id

def get_tuning_status(task_id: str):
    return _tasks.get(task_id, None)
