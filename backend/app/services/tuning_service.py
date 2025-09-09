import threading, uuid, itertools, time, json
import uuid
import itertools
import threading
import time
import json
from typing import Dict, Any
from ..services.backtest_service import run_backtest
from ..db import fetch_df, to_sql

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

    def worker():
        try:
            keys = list(params_grid.keys()) if params_grid else []
            grids = [params_grid[k] for k in keys] if params_grid else []
            for vals in itertools.product(*grids) if keys else [()]:
                p = {k:v for k,v in zip(keys, vals)} if keys else {}
                # call run_backtest; it persists runs and returns run_id
                run_id = run_backtest(code, start, end, strategy, p)
                _tasks[task_id]['runs'].append({'params':p, 'run_id': run_id})
                _tasks[task_id]['finished'] += 1
            _tasks[task_id]['status'] = 'finished'
        except Exception as e:
            _tasks[task_id]['status'] = 'error'
            _tasks[task_id]['error'] = str(e)

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    return task_id

def get_tuning_status(task_id: str):
    return _tasks.get(task_id, None)
