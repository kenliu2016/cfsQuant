import uuid
import pandas as pd
import numpy as np
import uuid
import json
from datetime import datetime
from ..db import fetch_df, execute, to_sql, get_engine
import importlib.util
from pathlib import Path
import logging

STRATEGY_DIR = Path(__file__).resolve().parents[2] / "core" / "strategies"
DEFAULT_BACKTEST_PARAMS = {
    "fee_rate": 0.0005,
    "slippage": 0.0002,
    "min_trade_amount": 100.0,       # 最小成交金额（货币单位）
    "min_trade_qty": 0.001,          # 最小成交数量（标的单位，0 表示不启用）
    "min_position_change": 0.01,     # 仓位变动门槛（绝对比例，例如 0.01 = 1%）
    "lot_size": 0.00001,             # 交易单位（如 100 股，或最小下单单位；0 表示不启用）
    "cooldown_bars": 530,           # 冷却期，单位 bar
    "initial_capital": 100000.0
}

logging.basicConfig(
    filename="backtest_trades_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
def log_trade_debug(action, price, qty, fee, slippage, position_cost, pnl=None):
    """
    打印每笔交易的详细信息到日志文件
    """
    logging.debug(
        f"ACTION={action}, PRICE={price:.2f}, QTY={qty}, "
        f"FEE={fee:.2f}, SLIPPAGE={slippage:.2f}, "
        f"POSITION_COST={position_cost:.2f}, "
        f"PNL={pnl if pnl is not None else 'N/A'}"
    )

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
        return {
            "run_id": backtest_id,
            "code": code,
            "start": start,
            "end": end,
            "strategy": strategy,
            "params": params or {},
            "nav": [],
        }

    mod = _load_strategy_module(strategy)
    default_params = getattr(mod, "DEFAULT_PARAMS", {})
    merged_params = {**DEFAULT_BACKTEST_PARAMS, **default_params, **(params or {})}

    fee_rate = float(merged_params.get("fee_rate", 0.0005))
    slippage = float(merged_params.get("slippage", 0.0002))
    min_trade_amount = float(merged_params.get("min_trade_amount", 100.0))
    min_trade_qty = float(merged_params.get("min_trade_qty", 0.0))
    min_position_change = float(merged_params.get("min_position_change", 0.01))
    lot_size = float(merged_params.get("lot_size", 0.0))
    cooldown_bars = int(merged_params.get("cooldown_bars", 0))
    initial_capital = float(merged_params.get("initial_capital", 100000.0))

    try:
        df = mod.run(df, merged_params)
    except Exception as e:
        raise RuntimeError(f"Strategy execution failed: {e}")

    if "position" not in df.columns:
        raise ValueError("Strategy must output 'position' column")

    data = df.reset_index()
    # 初始化变量
    cash = initial_capital
    current_pos_qty = 0.0
    avg_price = 0.0

    nav_list = []
    trades = []
    positions = []
    equity_curve = []

    last_trade_bar = -9999
    last_nav_val = None
    last_pos_qty = None

    for i, row in data.iterrows():
        dt = row["datetime"]
        price = float(row["close"])
        target_frac = float(row["position"])

        current_nav = cash + current_pos_qty * price
        target_value = current_nav * target_frac
        target_qty = 0.0 if price <= 0 else (target_value / price)
        delta_qty = target_qty - current_pos_qty

        # 冷却期检查
        if (i - last_trade_bar) <= cooldown_bars:
            delta_qty = 0.0

        # 仓位变动阈值检查
        prev_frac = 0.0 if current_nav == 0 else (current_pos_qty * price) / current_nav
        if abs(target_frac - prev_frac) < min_position_change:
            delta_qty = 0.0

        # 执行交易
        if abs(delta_qty) > 0:
            exec_price = price * (1 + slippage) if delta_qty > 0 else price * (1 - slippage)

            if delta_qty > 0:
                max_possible_qty = cash / (exec_price * (1 + fee_rate)) if exec_price > 0 else 0.0
                if delta_qty > max_possible_qty:
                    delta_qty = max_possible_qty
            else:
                if abs(delta_qty) > current_pos_qty:
                    delta_qty = -current_pos_qty

            # lot_size 四舍五入
            if lot_size and lot_size > 0:
                if delta_qty > 0:
                    delta_qty = (int(delta_qty / lot_size)) * lot_size
                else:
                    delta_qty = - (int(abs(delta_qty) / lot_size)) * lot_size

            amount = exec_price * delta_qty
            fee_amt = abs(amount) * fee_rate

            if abs(amount) < min_trade_amount or (min_trade_qty and abs(delta_qty) < min_trade_qty):
                delta_qty = 0.0

            if abs(delta_qty) > 0:
                cash -= (amount + fee_amt)

                realized_pnl = None
                side = "buy" if delta_qty > 0 else "sell"

                if delta_qty > 0:  # 买入
                    total_cost = avg_price * current_pos_qty + exec_price * delta_qty
                    current_pos_qty += delta_qty
                    avg_price = total_cost / current_pos_qty if current_pos_qty > 0 else 0.0
                else:  # 卖出
                    realized_pnl = (exec_price - avg_price) * abs(delta_qty) - fee_amt
                    current_pos_qty += delta_qty
                    # 卖出后 avg_price 保留卖出前持仓均价

                nav_val = cash + current_pos_qty * price

                # trades 记录
                trades.append({
                    "run_id": backtest_id,
                    "datetime": dt,
                    "code": code,
                    "side": side,
                    "price": float(exec_price),
                    "qty": float(delta_qty),
                    "amount": float(amount),
                    "fee": float(fee_amt),
                    "avg_price": float(avg_price),
                    "nav": float(nav_val),
                    "realized_pnl": float(realized_pnl) if realized_pnl is not None else None,
                })

                    # equity_curve 记录（方案 A：仅交易时）
                peak = nav_val if not equity_curve else max(nav_val, equity_curve[-1]["nav"])
                drawdown = nav_val / peak - 1 if peak > 0 else 0
                equity_curve.append({
                    "run_id": backtest_id,
                    "datetime": dt,
                    "nav": float(nav_val),
                    "drawdown": float(drawdown),
                })

                # 调试日志
                log_trade_debug(
                    action=side.upper(),
                    price=exec_price,
                    qty=delta_qty,
                    fee=fee_amt,
                    slippage=slippage,
                    position_cost=avg_price,
                    pnl=realized_pnl
                )

                last_trade_bar = i

        # positions 记录（方案 A）
        if last_pos_qty is None or current_pos_qty != last_pos_qty:
            positions.append({
                "run_id": backtest_id,
                "datetime": dt,
                "code": code,
                "qty": float(current_pos_qty),
                "avg_price": float(avg_price),
            })
            last_pos_qty = current_pos_qty

        nav_val = cash + current_pos_qty * price
        # 将当前净值添加到nav_list
        nav_list.append(nav_val)

    nav_series = pd.Series(nav_list, index=data["datetime"])

    # ==== 保存到数据库 ====
    engine = get_engine()
    # 首先保存run_id到runs表，以满足外键约束
    if nav_list:
        final_capital = nav_list[-1]
        # 使用to_sql方式插入数据
        run_data = pd.DataFrame([{
            'run_id': backtest_id,
            'strategy': strategy,
            'code': code,
            'start_time': start,
            'end_time': end,
            'initial_capital': initial_capital,
            'final_capital': final_capital,
            'paras': json.dumps(merged_params)
        }])
        run_data.to_sql('runs', con=engine, if_exists='append', index=False)

    if trades:
        trades_df = pd.DataFrame(
            trades,
            columns=[
                "run_id", "datetime", "code", "side", "price", "qty", "amount",
                "fee", "avg_price", "nav", "realized_pnl"
            ]
        )
        trades_df.to_sql("trades", con=engine, if_exists="append", index=False)

    
    if positions:
        pos_df = pd.DataFrame(positions, columns=["run_id", "datetime", "code", "qty", "avg_price"])
        pos_df.to_sql("positions", con=engine, if_exists="append", index=False)
    
    if equity_curve:
        eq_df = pd.DataFrame(equity_curve, columns=["run_id", "datetime", "nav", "drawdown"])
        eq_df.to_sql("equity_curve", con=engine, if_exists="append", index=False)

    # ==== 计算指标 metrics ====
    metrics = []
    if len(nav_list) > 1:
        final_return = nav_list[-1] / initial_capital - 1
        metrics.append({"run_id": backtest_id, "metric_name": "final_return", "metric_value": final_return})

        # 年化收益率
        days = (data["datetime"].iloc[-1] - data["datetime"].iloc[0]).days
        if days > 0:
            ann_return = (1 + final_return) ** (365.0 / days) - 1
            metrics.append({"run_id": backtest_id, "metric_name": "annual_return", "metric_value": ann_return})

        # 最大回撤
        dd = min([ec["drawdown"] for ec in equity_curve])
        metrics.append({"run_id": backtest_id, "metric_name": "max_drawdown", "metric_value": dd})

        # 夏普比率
        nav_series = pd.Series(nav_list).pct_change().dropna()
        if not nav_series.empty and nav_series.std() > 0:
            sharpe = np.sqrt(252) * nav_series.mean() / nav_series.std()
            metrics.append({"run_id": backtest_id, "metric_name": "sharpe", "metric_value": sharpe})

    if metrics:
        metrics_df = pd.DataFrame(metrics, columns=["run_id", "metric_name", "metric_value"])
        metrics_df.to_sql("metrics", con=engine, if_exists="append", index=False)

    return {
        "run_id": backtest_id,
        "code": code,
        "start": start,
        "end": end,
        "strategy": strategy,
        "params": merged_params,
        "nav": nav_series,
    }

def get_backtest_result(backtest_id: str):
    from ..db import fetch_df
    df_m = fetch_df("SELECT metric_name, metric_value FROM metrics WHERE run_id=:rid", rid=backtest_id)
    # 从equity_curve表读取数据，equity_curve表全面取代equity表
    df_e = fetch_df("SELECT datetime, nav, drawdown FROM equity_curve WHERE run_id=:rid ORDER BY datetime", rid=backtest_id)
    return {'metrics': df_m.to_dict(orient='records'), 'equity': df_e.to_dict(orient='records')}
