import os
from pathlib import Path
from ..db import fetch_df
STRATEGY_DIR = Path(__file__).resolve().parents[2] / "core" / "strategies"
def list_strategies():
    sql = """SELECT id, name, description, params::text AS params FROM strategies ORDER BY id""" 
    return fetch_df(sql)
def load_strategy_code(strategy_name: str) -> str:
    file_path = STRATEGY_DIR / f"{strategy_name}.py"
    if not file_path.exists():
        return f"# 文件不存在: {file_path}"
    return file_path.read_text(encoding="utf-8")
def save_strategy_code(strategy_name: str, code: str):
    file_path = STRATEGY_DIR / f"{strategy_name}.py"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code)
    return {"status": "ok", "path": str(file_path)}


def create_strategy(strategy_name: str, description: str = "", params: str = "{}"):
    file_path = STRATEGY_DIR / f"{strategy_name}.py"
    if file_path.exists():
        return {"status":"exists", "path": str(file_path)}
    # write a template file
    template = f'''"""Strategy: {strategy_name}

Template strategy. Edit `run(df, params)` to implement.
"""
import pandas as pd

DEFAULT_PARAMS = {{
    "short": 5,
    "long": 20,
    "fee_rate": 0.0005,
    "initial_capital": 100000.0,
    "max_position": 1.0,
    "slippage": 0.0
}}

def run(df: pd.DataFrame, params: dict):
    p = DEFAULT_PARAMS.copy()
    p.update(params or {{}})
    short = int(p.get("short",5))
    long = int(p.get("long",20))
    data = df.copy().sort_values("datetime").reset_index(drop=True)
    data["ma_s"] = data["close"].rolling(short, min_periods=1).mean()
    data["ma_l"] = data["close"].rolling(long, min_periods=1).mean()
    data["position"] = (data["ma_s"] > data["ma_l"]).astype(int)
    data["position"] = data["position"].shift(1).fillna(0).astype(int)
    return data
'''
    file_path.write_text(template, encoding='utf-8')
    # optionally insert into strategies table via DB, but here we leave it to existing init or DB admin
    return {"status":"ok", "path": str(file_path)}

def delete_strategy(strategy_name: str):
    file_path = STRATEGY_DIR / f"{strategy_name}.py"
    if file_path.exists():
        file_path.unlink()
        return {"status":"deleted", "path": str(file_path)}
    return {"status":"not_found"}
