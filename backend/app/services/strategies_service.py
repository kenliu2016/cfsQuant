from pathlib import Path
from ..db import fetch_df, get_engine
from sqlalchemy import text
import json
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
    
    # 从代码中提取DEFAULT_PARAMS并更新到数据库
    try:
        # 尝试提取DEFAULT_PARAMS
        import re
        params_match = re.search(r"DEFAULT_PARAMS\s*=\s*(\{[^}]*\})", code)
        if params_match:
            params_str = params_match.group(1)
            # 尝试解析参数
            try:
                params_dict = json.loads(params_str.replace("'", '"'))
                params_json = json.dumps(params_dict)
                
                # 更新数据库
                engine = get_engine()
                with engine.connect() as conn:
                    conn.execute(
                        text("UPDATE strategies SET params = :params WHERE name = :name"),
                        {
                            'name': strategy_name,
                            'params': params_json
                        }
                    )
                    conn.commit()
                print(f"成功: 策略参数已更新到数据库 - {strategy_name}")
            except Exception as e:
                print(f"警告: 解析或更新参数失败 - {e}")
    except Exception as e:
        print(f"警告: 提取参数失败 - {e}")
        
    return {"status": "ok", "path": str(file_path)}


def create_strategy(strategy_name: str, description: str = "", params: str = "{}"):
    file_path = STRATEGY_DIR / f"{strategy_name}.py"
    if file_path.exists():
        return {"status":"exists", "path": str(file_path)}
    
    # 定义DEFAULT_PARAMS，用于模板和数据库
    default_params = {
        "short": 5,
        "long": 20,
        "fee_rate": 0.0005,
        "initial_capital": 100000.0,
        "max_position": 1.0,
        "slippage": 0.0
    }
    
    # 将DEFAULT_PARAMS转换为JSON字符串，用于数据库存储
    params_json = json.dumps(default_params)
    
    # 编写模板文件
    template = f'''
"""Strategy: {strategy_name}

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
    
    # 写入文件
    file_path.write_text(template, encoding='utf-8')
    
    # 同步保存到数据库
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(
                text("INSERT INTO strategies (name, description, params) VALUES (:name, :description, :params)"),
                {
                    'name': strategy_name,
                    'description': description,
                    'params': params_json
                }
            )
            conn.commit()
    except Exception as e:
        print(f"警告: 数据库记录插入失败 - {e}")
        
    return {"status":"ok", "path": str(file_path)}

def delete_strategy(strategy_name: str):
    file_path = STRATEGY_DIR / f"{strategy_name}.py"
    file_deleted = False
    db_deleted = False
    
    # 删除文件
    if file_path.exists():
        file_path.unlink()
        file_deleted = True
    
    # 从数据库删除记录
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("DELETE FROM strategies WHERE name = :name"),
                {'name': strategy_name}
            )
            conn.commit()
            if result.rowcount > 0:
                db_deleted = True
    except Exception as e:
        print(f"警告: 数据库记录删除失败 - {e}")
    
    # 根据删除结果返回不同状态
    if file_deleted and db_deleted:
        return {"status":"deleted", "path": str(file_path), "db":"deleted"}
    elif file_deleted:
        return {"status":"file_deleted", "path": str(file_path), "db":"not_found"}
    elif db_deleted:
        return {"status":"db_deleted", "path": str(file_path), "db":"deleted"}
    else:
        return {"status":"not_found"}
