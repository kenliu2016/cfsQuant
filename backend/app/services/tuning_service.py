import threading, uuid, itertools, time, json
import uuid
import itertools
import threading
import time
import json
from typing import Dict, Any
import pandas as pd
from ..services.backtest_service import run_backtest
from ..db import fetch_df, to_sql, execute
from sqlalchemy import text

_tasks = {}  # task_id -> status dict

def start_tuning_async(strategy: str, code: str, start: str, end: str, params_grid: Dict[str, list]):
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
            for vals in itertools.product(*grids) if keys else [()]:
                p = {k:v for k,v in zip(keys, vals)} if keys else {}
                # call run_backtest; it persists runs and returns run_id
                backtest_result = run_backtest(code, start, end, strategy, p)
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
                        execute(text(f"UPDATE tuning_tasks SET finished = {_tasks[task_id]['finished']} WHERE task_id = '{db_task_id}'"))
                    except Exception as e:
                        print(f"Error updating tuning task status: {e}")
                        
            _tasks[task_id]['status'] = 'finished'
            # 更新最终状态
            if db_task_id:
                try:
                    execute(text(f"UPDATE tuning_tasks SET status = 'finished' WHERE task_id = '{db_task_id}'"))
                except Exception as e:
                    print(f"Error updating tuning task status: {e}")
        except Exception as e:
            _tasks[task_id]['status'] = 'error'
            _tasks[task_id]['error'] = str(e)
            # 更新错误状态
            db_task_id = _tasks[task_id].get('db_id')
            if db_task_id:
                try:
                    execute(text(f"UPDATE tuning_tasks SET status = 'error' WHERE task_id = '{db_task_id}'"))
                except Exception as e:
                    print(f"Error updating tuning task status: {e}")

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    return task_id

def get_tuning_status(task_id: str):
    return _tasks.get(task_id, None)
