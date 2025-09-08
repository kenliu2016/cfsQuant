import uuid
import pandas as pd
import numpy as np
from datetime import datetime
from ..db import fetch_df, execute, to_sql
import importlib.util
from pathlib import Path

STRATEGY_DIR = Path(__file__).resolve().parents[2] / "core" / "strategies"

def _load_data(code: str, start: str, end: str):
    sql = """
    SELECT datetime, open, high, low, close, volume
    FROM minute_realtime
    WHERE code=:code AND datetime BETWEEN :start AND :end
    ORDER BY datetime
    """
    df = fetch_df(sql, code=code, start=start, end=end)
    if "datetime" in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
    return df

def _calc_metrics(equity: pd.Series, rf: float = 0.0, periods_per_year: int = 252):
    # equity is NAV series
    ret = equity.pct_change().fillna(0.0)
    total_ret = float(equity.iloc[-1] / equity.iloc[0] - 1) if len(equity) > 1 else 0.0
    ann_ret = (1 + total_ret) ** (periods_per_year / len(equity)) - 1 if len(equity) > 1 else 0.0
    vol = ret.std() * np.sqrt(periods_per_year) if len(ret) > 1 else 0.0
    sharpe = (ann_ret - rf) / vol if vol > 0 else 0.0
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    max_dd = float(drawdown.min()) if len(drawdown) > 0 else 0.0
    return {
        "total_return": total_ret,
        "annual_return": ann_ret,
        "max_drawdown": max_dd,
        "sharpe": sharpe
    }, drawdown

def _load_strategy_module(strategy_name: str):
    path = STRATEGY_DIR / f"{strategy_name}.py"
    if not path.exists():
        raise FileNotFoundError(f"Strategy file not found: {path}")
    spec = importlib.util.spec_from_file_location(f"strategies.{strategy_name}", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def run_backtest(code: str, start: str, end: str, strategy: str, params: dict):
    """Pluggable strategy backtest with fractional position sizing, slippage and fees."""
    backtest_id = str(uuid.uuid4())
    df = _load_data(code, start, end)
    if df.empty:
        to_sql(pd.DataFrame([{'run_id': backtest_id, 'strategy': strategy, 'code': code, 'start_time': start, 'end_time': end, 'initial_capital': params.get('initial_capital', 100000.0), 'final_capital': params.get('initial_capital', 100000.0)}]), 'runs')
        return backtest_id

    # load strategy module
    try:
        mod = _load_strategy_module(strategy)
    except Exception as e:
        to_sql(pd.DataFrame([{'run_id': backtest_id, 'strategy': strategy, 'code': code, 'start_time': start, 'end_time': end, 'initial_capital': params.get('initial_capital', 100000.0), 'final_capital': params.get('initial_capital', 100000.0)}]), 'runs')
        raise

    # run strategy
    strat_df = mod.run(df.copy(), params or {})
    if 'position' not in strat_df.columns:
        raise ValueError("Strategy must return a DataFrame with a 'position' column (fractional 0..1)")

    data = strat_df.copy().sort_values("datetime").reset_index(drop=True)
    data['ret'] = data['close'].pct_change().fillna(0.0)
    # ensure fractional position between 0 and 1
    data['position'] = data['position'].clip(0.0,1.0).astype(float)

    # parameters
    slippage = float(params.get('slippage', getattr(mod, 'DEFAULT_PARAMS', {}).get('slippage', 0.0)))
    fee_rate = float(params.get('fee_rate', getattr(mod, 'DEFAULT_PARAMS', {}).get('fee_rate', 0.0005)))
    initial_capital = float(params.get('initial_capital', getattr(mod, 'DEFAULT_PARAMS', {}).get('initial_capital', 100000.0)))

    cash = initial_capital
    nav = []
    trades = []
    current_pos_qty = 0.0  # number of shares held
    # iterate each bar and adjust to target percent of INITIAL capital
    for i, row in data.iterrows():
        price = float(row['close'])
        target_frac = float(row['position'])
        target_value = initial_capital * target_frac
        target_qty = 0.0 if price <= 0 else (target_value / price)
        prev_qty = current_pos_qty
        delta_qty = target_qty - prev_qty
        if abs(delta_qty) > 0:
            # apply slippage
            exec_price = price * (1 + slippage) if delta_qty > 0 else price * (1 - slippage)
            amount = exec_price * delta_qty
            fee_amt = abs(amount) * fee_rate
            cash -= amount + fee_amt
            current_pos_qty = target_qty
            trades.append({'run_id': backtest_id, 'datetime': row['datetime'].strftime('%Y-%m-%d %H:%M:%S'), 'code': code, 'side': 'BUY' if delta_qty>0 else 'SELL', 'price': exec_price, 'qty': float(delta_qty), 'amount': float(amount), 'fee': float(fee_amt)})
        nav_val = cash + current_pos_qty * price
        nav.append(nav_val)

    equity = pd.Series(nav)
    if equity.empty:
        equity = pd.Series([initial_capital])

    metrics, dd = _calc_metrics(equity)

    # persist run
    run_row = {'run_id': backtest_id, 'strategy': strategy, 'code': code, 'start_time': start, 'end_time': end, 'initial_capital': initial_capital, 'final_capital': float(equity.iloc[-1])}
    to_sql(pd.DataFrame([run_row]), 'runs')
    # persist metrics
    mrows = [{'run_id': backtest_id, 'metric_name': k, 'metric_value': float(v)} for k, v in metrics.items()]
    if mrows:
        to_sql(pd.DataFrame(mrows), 'metrics')
    # persist equity (align to data datetimes; if len mismatch use last known)
    eq_datetimes = data['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
    if len(eq_datetimes) != len(equity):
        # pad/match lengths
        eq_datetimes = eq_datetimes[:len(equity)]
    erows = pd.DataFrame({'run_id': backtest_id, 'datetime': eq_datetimes, 'nav': equity.values, 'drawdown': dd.values})
    to_sql(erows, 'equity')
    # persist trades
    if trades:
        to_sql(pd.DataFrame(trades), 'trades')

    return backtest_id

def get_backtest_result(backtest_id: str):
    from ..db import fetch_df
    df_m = fetch_df("SELECT metric_name, metric_value FROM metrics WHERE run_id=:rid", rid=backtest_id)
    df_e = fetch_df("SELECT datetime, nav, drawdown FROM equity WHERE run_id=:rid ORDER BY datetime", rid=backtest_id)
    return {'metrics': df_m.to_dict(orient='records'), 'equity': df_e.to_dict(orient='records')}
