import threading, uuid, time
from typing import Dict, Any
from ..services.backtest_service import _load_data, _load_strategy_module
# simple in-memory monitors: id -> dict(status, latest_signal, logs, running)
_monitors = {}

def start_monitor(strategy: str, code: str, start_time: str, interval_sec: int = 10):
    monitor_id = str(uuid.uuid4())
    _monitors[monitor_id] = {'strategy': strategy, 'code': code, 'start_time': start_time, 'interval': interval_sec, 'running': True, 'latest': None, 'logs': []}

    def worker():
        try:
            mod = _load_strategy_module(strategy)
        except Exception as e:
            _monitors[monitor_id]['running'] = False
            _monitors[monitor_id]['logs'].append({'ts':time.time(), 'msg': f'strategy_load_error: {e}'})
            return
        while _monitors[monitor_id]['running']:
            try:
                # load recent data from start_time to now; using _load_data helper
                import datetime as _dt
                end = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                df = _load_data(code, _monitors[monitor_id]['start_time'], end)
                if df is None or df.empty:
                    _monitors[monitor_id]['logs'].append({'ts':time.time(), 'msg':'no_data'})
                else:
                    res = mod.run(df.copy(), {})
                    # take last position value as latest signal
                    if 'position' in res.columns:
                        last = float(res.sort_values('datetime').iloc[-1]['position'])
                        _monitors[monitor_id]['latest'] = {'datetime': res.sort_values('datetime').iloc[-1]['datetime'].strftime('%Y-%m-%d %H:%M:%S'), 'position': last}
                        _monitors[monitor_id]['logs'].append({'ts':time.time(), 'msg':f'pos={last}'})
                    else:
                        _monitors[monitor_id]['logs'].append({'ts':time.time(), 'msg':'no_position_col'})
            except Exception as e:
                _monitors[monitor_id]['logs'].append({'ts':time.time(), 'msg':str(e)})
            time.sleep(interval_sec)
        _monitors[monitor_id]['running'] = False

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    return monitor_id

def stop_monitor(monitor_id: str):
    if monitor_id in _monitors:
        _monitors[monitor_id]['running'] = False
        return True
    return False

def get_monitor(monitor_id: str):
    return _monitors.get(monitor_id)
