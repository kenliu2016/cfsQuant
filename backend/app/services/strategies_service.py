from pathlib import Path
from ..db import fetch_df, get_engine
from sqlalchemy import text
import json
import time
from pathlib import Path
import logging

# 配置日志
logger = logging.getLogger(__name__)

STRATEGY_DIR = Path(__file__).resolve().parents[2] / "core" / "strategies"

# 添加内存缓存机制
_cached_strategies = None
_cached_timestamp = 0
CACHE_EXPIRE_TIME = 30  # 缓存过期时间，单位：秒（从5分钟缩短为30秒，提高新策略可见性）

# 添加异步版本的列表策略函数，优化性能
async def alist_strategies():
    """异步获取策略列表，用于API调用"""
    # 使用单独的异步实现，避免阻塞
    import pandas as pd
    from ..db import fetch_df_async
    
    # 全局变量声明
    global _cached_strategies, _cached_timestamp
    
    # 先检查内存缓存
    current_time = time.time()
    if _cached_strategies is not None and current_time - _cached_timestamp < CACHE_EXPIRE_TIME:
        logger.debug("使用内存缓存的策略列表")
        return _cached_strategies.copy()  # 返回副本避免修改缓存数据
    
    try:
        # 缓存过期或不存在，从数据库查询
        logger.debug("从数据库查询策略列表")
        sql = """SELECT id, name, description, params::text AS params FROM strategies ORDER BY id"""
        df = await fetch_df_async(sql)
        
        # 更新内存缓存
        _cached_strategies = df
        _cached_timestamp = current_time
        
        return df
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        # 出错时如果有缓存，返回缓存数据
        if _cached_strategies is not None:
            return _cached_strategies.copy()
        # 否则返回空DataFrame
        return pd.DataFrame(columns=['id', 'name', 'description', 'params'])

def list_strategies():
    """同步获取策略列表，用于非异步环境"""
    global _cached_strategies, _cached_timestamp
    
    # 检查缓存是否有效
    current_time = time.time()
    if _cached_strategies is not None and current_time - _cached_timestamp < CACHE_EXPIRE_TIME:
        logger.debug("使用内存缓存的策略列表")
        return _cached_strategies.copy()  # 返回副本避免修改缓存数据
    
    # 缓存过期或不存在，从数据库查询
    logger.debug("从数据库查询策略列表")
    sql = """SELECT id, name, description, params::text AS params FROM strategies ORDER BY id"""
    df = fetch_df(sql)
    
    # 更新缓存
    _cached_strategies = df
    _cached_timestamp = current_time
    
    return df

# 提供清除缓存的函数，用于策略有变更时

def clear_strategies_cache():
    global _cached_strategies, _cached_timestamp
    _cached_strategies = None
    _cached_timestamp = 0

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
        # 使用Python re模块支持的语法匹配DEFAULT_PARAMS = { ... }
        import re
        # 使用非贪婪匹配来处理多行参数定义
        params_match = re.search(r"DEFAULT_PARAMS\s*=\s*(\{.*?\})", code, re.DOTALL)
        
        if params_match:
            params_str = params_match.group(1)
            logger.debug(f"提取到参数字符串: {params_str}")
            
            # 尝试解析参数
            try:
                # 处理参数中的注释（JSON解析器不支持注释）
                # 先移除行尾注释
                lines = params_str.split('\n')
                cleaned_lines = []
                for line in lines:
                    # 找到行中第一个#的位置，如果存在则截断
                    comment_pos = line.find('#')
                    if comment_pos != -1:
                        # 保留#之前的部分并去除首尾空白
                        cleaned_line = line[:comment_pos].strip()
                        if cleaned_line:
                            cleaned_lines.append(cleaned_line)
                    else:
                        cleaned_lines.append(line.strip())
                
                # 重新组合成字符串
                cleaned_params_str = '\n'.join(cleaned_lines)
                logger.debug(f"去除注释后的参数: {cleaned_params_str}")
                
                # 尝试解析清理后的JSON
                # 1. 处理Python风格的布尔值 (True/False -> true/false)
                json_friendly_str = cleaned_params_str.replace('True', 'true').replace('False', 'false')
                
                # 2. 处理末尾多余的逗号
                # 匹配模式：任何行末的逗号，后面跟右花括号或换行
                import re
                json_friendly_str = re.sub(r',\s*(}|$)', '\g<1>', json_friendly_str)
                
                logger.debug(f"JSON友好格式参数: {json_friendly_str}")
                
                try:
                    params_dict = json.loads(json_friendly_str)
                except json.JSONDecodeError:
                    # 如果失败，尝试将单引号替换为双引号后再解析
                    try:
                        params_dict = json.loads(json_friendly_str.replace("'", '"'))
                    except json.JSONDecodeError as e:
                        logger.error(f"参数解析失败: {e}, JSON友好格式参数: {json_friendly_str}")
                        raise
                
                params_json = json.dumps(params_dict)
                logger.debug(f"解析后的参数: {params_json}")
                
                # 更新数据库
                engine = get_engine()
                with engine.connect() as conn:
                    result = conn.execute(
                        text("UPDATE strategies SET params = :params WHERE name = :name"),
                        {
                            'name': strategy_name,
                            'params': params_json
                        }
                    )
                    conn.commit()
                    
                    # 检查是否有记录被更新
                    if result.rowcount > 0:
                        logger.info(f"成功更新策略 [{strategy_name}] 的参数到数据库")
                    else:
                        logger.warning(f"策略 [{strategy_name}] 在数据库中不存在，无法更新参数")
                        # 尝试插入新记录
                        try:
                            conn.execute(
                                text("INSERT INTO strategies (name, description, params) VALUES (:name, '', :params)"),
                                {'name': strategy_name, 'params': params_json}
                            )
                            conn.commit()
                            logger.info(f"成功在数据库中创建策略 [{strategy_name}] 的记录")
                        except Exception as e:
                            logger.error(f"创建策略记录失败: {e}")
            except Exception as e:
                logger.error(f"提取或更新参数时出错: {e}")
        else:
            logger.warning(f"在策略代码中未找到DEFAULT_PARAMS定义")
    except Exception as e:
        logger.error(f"处理策略参数时出错: {e}")
    
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
