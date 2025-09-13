import uuid
import pandas as pd
import numpy as np
import json
from datetime import datetime
from ..db import fetch_df, to_sql, get_engine
import importlib.util
from pathlib import Path
import logging
import os

STRATEGY_DIR = Path(__file__).resolve().parents[2] / "core" / "strategies"
DEFAULT_BACKTEST_PARAMS = {
    "initial_capital": 1000000.0, # (引擎参数)初始资金
    "fee_rate": 0.001,           # (引擎参数)手续费率（每笔交易的固定成本）
    "slippage": 0.0002,           # (引擎参数)滑点（交易价格的偏移量，模拟真实交易环境）
    "min_trade_amount": 5000.0,   # (引擎参数)最小成交金额（货币单位）
    "min_trade_qty": 0.01,       # (引擎参数)最小成交数量（标的单位，0 表示不启用）
    "min_position_change": 0.05,  # 【已优化】仓位变动门槛从20%降低到2%，更合理
    "lot_size": 0.0001,           # (引擎参数)最小交易数量（如100股，或最小下单单位；0 表示不启用）
    "cooldown_bars": 240,         # (引擎参数)冷却周期（单位bar）
    "stop_loss_pct": 0.25,        # (引擎参数)跌破下限百分比止损
    "take_profit_pct": 0.15,      # (引擎参数)超过收益百分比止盈
    "logging_enabled": False,      # (通用参数)日志总开关
}

# --- 日志记录器配置 ---
service_dir = os.path.dirname(os.path.abspath(__file__))
backtest_dir = os.path.dirname(os.path.dirname(os.path.dirname(service_dir)))
logs_dir = os.path.join(backtest_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(logs_dir, "backtest_trades_debug.log")
backtest_logger = logging.getLogger("backtest_service")
backtest_logger.setLevel(logging.DEBUG)
for handler in backtest_logger.handlers[:]:
    backtest_logger.removeHandler(handler)
file_handler = logging.FileHandler(log_file, mode='w') # 使用'w'模式在每次回测时覆盖日志
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(formatter)
backtest_logger.addHandler(file_handler)
backtest_logger.propagate = False

# 全局日志开关状态
global_logging_enabled = True

# --- 日志记录器配置结束 ---


def log_trade_debug(action, price, qty, fee, slippage, position_cost, trade_type, pnl=None, datetime=None):
    """
    打印每笔交易的详细信息到日志文件
    """
    if not global_logging_enabled:
        return
        
    def safe_format(value, format_str):
        if value is None or pd.isna(value) or np.isnan(value):
            return 'N/A'
        try:
            return format_str.format(value)
        except (ValueError, TypeError):
            return str(value)
    
    backtest_logger.debug(
        f"DATETIME={datetime if datetime is not None else 'N/A'}, "
        f"ACTION={action}, TRADE_TYPE={trade_type}, PRICE={safe_format(price, '{:.2f}')}, QTY={safe_format(qty, '{}')}, "
        f"FEE={safe_format(fee, '{:.2f}')}, SLIPPAGE={safe_format(slippage, '{:.6f}')}, "
        f"POSITION_COST={safe_format(position_cost, '{:.2f}')}, "
        f"PNL={safe_format(pnl, '{:.2f}') if pnl is not None else 'N/A'}"
    )

def log_info(message):
    """
    带开关的info日志记录
    """
    if global_logging_enabled:
        backtest_logger.info(message)

def log_debug(message):
    """
    带开关的debug日志记录
    """
    if global_logging_enabled:
        backtest_logger.debug(message)

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
        return {"run_id": backtest_id, "nav": []}

    mod = _load_strategy_module(strategy)
    default_params = getattr(mod, "DEFAULT_PARAMS", {})
    merged_params = {**DEFAULT_BACKTEST_PARAMS, **default_params, **(params or {})}

    # 根据参数设置全局日志开关状态
    global global_logging_enabled
    global_logging_enabled = bool(merged_params.get("logging_enabled", True))
    
    # 即使日志关闭，也要记录日志开关状态，以便调试
    if global_logging_enabled:
        log_info(f"回测参数已合并 - 策略: {strategy}, 标的: {code}")
        log_info(f"合并后的完整参数: {json.dumps(merged_params, ensure_ascii=False)}")

    fee_rate = float(merged_params.get("fee_rate", 0.0005))
    base_slippage = float(merged_params.get("slippage", 0.0002))
    min_trade_amount = float(merged_params.get("min_trade_amount", 5000.0))
    min_trade_qty = float(merged_params.get("min_trade_qty", 0.0))
    min_position_change = float(merged_params.get("min_position_change", 0.02))
    lot_size = float(merged_params.get("lot_size", 0.0))
    cooldown_bars = int(merged_params.get("cooldown_bars", 0))
    initial_capital = float(merged_params.get("initial_capital", 100000.0))
    stop_loss_pct = float(merged_params.get("stop_loss_pct", 0.15))
    take_profit_pct = float(merged_params.get("take_profit_pct", 0.25))

    try:
        # 保存原始datetime列，避免策略执行时丢失
        original_datetime = df['datetime'].copy()
        df = mod.run(df, merged_params)
        # 确保datetime列存在，如果不存在则恢复原始列
        if 'datetime' not in df.columns:
            df['datetime'] = original_datetime
    except Exception as e:
        raise RuntimeError(f"Strategy execution failed: {e}")
    if "position" not in df.columns:
        raise ValueError("Strategy must output 'position' column")

    data = df.reset_index()
    cash = initial_capital
    current_pos_qty = 0.0
    avg_price = 0.0
    nav_list, trades, positions, equity_curve = [], [], [], []
    last_trade_bar = -9999
    last_pos_qty = None

    for i, row in data.iterrows():
        dt = row["datetime"]
        price = float(row["close"])
        nav_val = cash + current_pos_qty * price if not pd.isna(price) else cash

        # 【已优化】统一交易逻辑，引擎风控(SL/TP)优先于策略信号
        strategy_target_frac = float(row["position"])
        final_target_frac = strategy_target_frac
        trade_type = "normal"
        is_risk_trade = False

        if current_pos_qty > 0 and avg_price > 0 and not pd.isna(price):
            profit_pct = (price - avg_price) / avg_price
            
            if profit_pct >= take_profit_pct:
                current_value = current_pos_qty * price
                current_frac = current_value / nav_val if nav_val > 0 else 0
                final_target_frac = current_frac * 0.5 
                trade_type = "take_profit"
                is_risk_trade = True
                log_info(f"[{dt}] 触发止盈: 当前价={price:.2f}, 均价={avg_price:.2f}, 涨幅={profit_pct:.2%}")
            
            elif profit_pct <= -stop_loss_pct:
                final_target_frac = 0.0
                trade_type = "stop_loss"
                is_risk_trade = True
                log_info(f"[{dt}] 触发止损: 当前价={price:.2f}, 均价={avg_price:.2f}, 跌幅={profit_pct:.2%}")

        target_value = nav_val * final_target_frac
        target_qty = target_value / price if not (pd.isna(price) or price <= 0) else 0.0
        delta_qty = target_qty - current_pos_qty

        if not is_risk_trade:
            if (i - last_trade_bar) <= cooldown_bars:
                delta_qty = 0.0
            else:
                prev_frac = (current_pos_qty * price) / nav_val if nav_val > 0 else 0.0
                if abs(final_target_frac - prev_frac) < min_position_change:
                    delta_qty = 0.0
        
        tr = max(row["high"] - row["low"], abs(row["high"] - data.iloc[i-1]["close"]) if i > 0 else 0, abs(row["low"] - data.iloc[i-1]["close"]) if i > 0 else 0) if not (pd.isna(row["high"]) or pd.isna(row["low"])) else 0.0
        volatility_factor = tr / price if not (pd.isna(price) or price <= 0) else 0.0
        dynamic_slippage = base_slippage * (1 + volatility_factor * 2.0)
        
        if lot_size > 0 and not pd.isna(delta_qty):
            delta_qty = np.floor(abs(delta_qty) / lot_size) * lot_size * np.sign(delta_qty)
        if min_trade_qty > 0 and abs(delta_qty) < min_trade_qty:
            delta_qty = 0.0
        
        if abs(delta_qty) > 1e-9:
            if pd.isna(price): continue
            
            exec_price = price * (1 + dynamic_slippage) if delta_qty > 0 else price * (1 - dynamic_slippage)
            if pd.isna(exec_price) or exec_price <= 0: continue
            
            if delta_qty > 0:
                max_possible_qty = cash / (exec_price * (1 + fee_rate))
                delta_qty = min(delta_qty, max_possible_qty)
            else:
                delta_qty = -min(abs(delta_qty), current_pos_qty)

            if abs(delta_qty) < 1e-9: continue
            
            amount = exec_price * delta_qty
            fee_amt = abs(amount) * fee_rate

            if abs(amount) < min_trade_amount and not is_risk_trade:
                continue

            cash -= (amount + fee_amt)
            realized_pnl = None
            side = "buy" if delta_qty > 0 else "sell"

            if side == "buy":
                total_cost = avg_price * current_pos_qty + exec_price * delta_qty
                current_pos_qty += delta_qty
                avg_price = total_cost / current_pos_qty if current_pos_qty > 0 else 0.0
            else:
                realized_pnl = (exec_price - avg_price) * abs(delta_qty) - fee_amt
                current_pos_qty += delta_qty
                if current_pos_qty < 1e-9:
                    current_pos_qty = 0.0
                    avg_price = 0.0

            nav_val = cash + current_pos_qty * price
            
            trades.append({
                "run_id": backtest_id, "datetime": dt, "code": code, "side": side,
                "trade_type": trade_type, "price": float(exec_price), "qty": float(delta_qty),
                "amount": float(amount), "fee": float(fee_amt), "avg_price": float(avg_price),
                "nav": float(nav_val), "realized_pnl": float(realized_pnl) if pd.notna(realized_pnl) else None,
            })

            log_trade_debug(action=side.upper(), trade_type=trade_type, price=exec_price, qty=delta_qty,
                            fee=fee_amt, slippage=dynamic_slippage, position_cost=avg_price,
                            pnl=realized_pnl, datetime=dt)
            last_trade_bar = i

        if not pd.isna(nav_val):
            peak = nav_val if not equity_curve else max(nav_val, equity_curve[-1]["nav"])
            drawdown_val = nav_val / peak - 1 if peak > 0 else 0
            equity_curve.append({"run_id": backtest_id, "datetime": dt, "nav": float(nav_val), "drawdown": float(drawdown_val)})
        
        if last_pos_qty is None or abs(current_pos_qty - last_pos_qty) > 1e-9:
            positions.append({"run_id": backtest_id, "datetime": dt, "code": code, "qty": float(current_pos_qty), "avg_price": float(avg_price)})
            last_pos_qty = current_pos_qty

        nav_list.append(nav_val)

    nav_series = pd.Series(nav_list, index=data["datetime"])
    engine = get_engine()
    if nav_list:
        final_capital = nav_list[-1]
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
                "run_id", "datetime", "code", "side", "trade_type", "price", "qty", "amount",
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

    # === 【已优化】修正盈亏归因分析 ===
    metrics = []
    if len(nav_list) > 1:
        final_return = nav_list[-1] / initial_capital - 1
        metrics.append({"run_id": backtest_id, "metric_name": "final_return", "metric_value": final_return})
        days = (data["datetime"].iloc[-1] - data["datetime"].iloc[0]).days
        if days > 0:
            ann_return = (1 + final_return) ** (365.0 / days) - 1
            metrics.append({"run_id": backtest_id, "metric_name": "annual_return", "metric_value": ann_return})
        dd = min([ec["drawdown"] for ec in equity_curve])
        metrics.append({"run_id": backtest_id, "metric_name": "max_drawdown", "metric_value": dd})
        nav_series_pct_change = pd.Series(nav_list).pct_change().dropna()
        if not nav_series_pct_change.empty and nav_series_pct_change.std() > 0:
            sharpe = np.sqrt(252) * nav_series_pct_change.mean() / nav_series_pct_change.std()
            metrics.append({"run_id": backtest_id, "metric_name": "sharpe", "metric_value": sharpe})
    if trades:
        trades_df_final = pd.DataFrame(trades)
        closed_trades_df = trades_df_final[trades_df_final['side'] == 'sell'].copy()
        
        if not closed_trades_df.empty:
            # `realized_pnl` 在记录时已包含手续费，无需重复计算
            trade_attribution = closed_trades_df.groupby('trade_type').agg(
                total_pnl=('realized_pnl', 'sum'),
                total_trades=('realized_pnl', 'count'),
                winning_trades=('realized_pnl', lambda pnl: (pnl > 0).sum())
            ).reset_index()

            if not trade_attribution.empty:
                trade_attribution['win_rate'] = (trade_attribution['winning_trades'] / trade_attribution['total_trades']).fillna(0)
                trade_attribution['avg_pnl'] = (trade_attribution['total_pnl'] / trade_attribution['total_trades']).fillna(0)
            
                log_info("盈亏归因分析结果:")
                log_info(trade_attribution.to_string(index=False))

                attribution_metrics = []
                for _, row in trade_attribution.iterrows():
                    ttype = row['trade_type']
                    attribution_metrics.extend([
                        {"run_id": backtest_id, "metric_name": f"attribution_{ttype}_total_pnl", "metric_value": row['total_pnl']},
                        {"run_id": backtest_id, "metric_name": f"attribution_{ttype}_total_trades", "metric_value": row['total_trades']},
                        {"run_id": backtest_id, "metric_name": f"attribution_{ttype}_win_rate", "metric_value": row['win_rate']},
                        {"run_id": backtest_id, "metric_name": f"attribution_{ttype}_avg_pnl", "metric_value": row['avg_pnl']}
                    ])     
                metrics.extend(attribution_metrics)

    if metrics:
        metrics_df = pd.DataFrame(metrics)
        metrics_df.to_sql("metrics", con=engine, if_exists="append", index=False)

    return {
        "run_id": backtest_id, "code": code, "start": start, "end": end,
        "strategy": strategy, "params": merged_params, "nav": nav_series,
        "metrics": pd.DataFrame(metrics).set_index('metric_name')['metric_value'].to_dict() if metrics else {}
    }

def get_backtest_result(backtest_id: str):
    from ..db import fetch_df
    df_m = fetch_df("SELECT metric_name, metric_value FROM metrics WHERE run_id=:rid", rid=backtest_id)
    df_e = fetch_df("SELECT datetime, nav, drawdown FROM equity_curve WHERE run_id=:rid ORDER BY datetime", rid=backtest_id)
    return {'metrics': df_m.to_dict(orient='records'), 'equity': df_e.to_dict(orient='records')}