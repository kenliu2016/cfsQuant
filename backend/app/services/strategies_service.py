import json
import time
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from sqlalchemy import text

from common.db import fetch_df, get_engine
from common import LoggerFactory
from ..main.tenant_context import get_current_tenant

# 使用LoggerFactory替换原有logger
logger = LoggerFactory.get_logger('strategies_service')

STRATEGY_DIR = Path(__file__).resolve().parents[2] / "strategies"

# 添加内存缓存机制（按租户区分）
_cached_strategies: Dict[str, pd.DataFrame] = {}
_cached_timestamp: Dict[str, float] = {}
CACHE_EXPIRE_TIME = 30  # 缓存过期时间，单位：秒（从5分钟缩短为30秒，提高新策略可见性）

# 添加异步版本的列表策略函数，优化性能
async def alist_strategies(tenant_id: Optional[str] = None) -> pd.DataFrame:
    """异步获取策略列表，用于API调用"""
    from common.db import fetch_df_async

    tenant = tenant_id or get_current_tenant()
    cache_key = tenant
    current_time = time.time()

    cached_df = _cached_strategies.get(cache_key)
    cached_ts = _cached_timestamp.get(cache_key, 0)
    if cached_df is not None and current_time - cached_ts < CACHE_EXPIRE_TIME:
        logger.info("使用租户 %s 的内存缓存策略列表", tenant)
        return cached_df.copy()

    sql = """
    SELECT id, name, description, params::text AS params
    FROM sys_strategies
    WHERE tenant_id = :tenant_id
    ORDER BY id
    """

    try:
        logger.info("从数据库查询租户 %s 的策略列表", tenant)
        df = await fetch_df_async(sql, tenant_id=tenant)
        if df.empty:
            # 回退到同步查询以防异步连接池丢失
            df = fetch_df(sql, tenant_id=tenant)
        _cached_strategies[cache_key] = df
        _cached_timestamp[cache_key] = current_time
        return df
    except Exception as exc:
        logger.error("获取租户 %s 策略列表失败: %s", tenant, exc, exc_info=True)
        fallback = _cached_strategies.get(cache_key)
        if fallback is not None:
            return fallback.copy()
        return pd.DataFrame(columns=['id', 'name', 'description', 'params'])

def list_strategies(tenant_id: Optional[str] = None) -> pd.DataFrame:
    """同步获取策略列表，用于非异步环境"""
    tenant = tenant_id or get_current_tenant()
    cache_key = tenant
    current_time = time.time()

    cached_df = _cached_strategies.get(cache_key)
    cached_ts = _cached_timestamp.get(cache_key, 0)
    if cached_df is not None and current_time - cached_ts < CACHE_EXPIRE_TIME:
        logger.debug("使用租户 %s 的内存缓存策略列表", tenant)
        return cached_df.copy()

    sql = """
    SELECT id, name, description, params::text AS params
    FROM sys_strategies
    WHERE tenant_id = :tenant_id
    ORDER BY id
    """
    df = fetch_df(sql, tenant_id=tenant)
    _cached_strategies[cache_key] = df
    _cached_timestamp[cache_key] = current_time
    return df

# 提供清除缓存的函数，用于策略有变更时

def clear_strategies_cache(tenant_id: Optional[str] = None) -> None:
    if tenant_id:
        _cached_strategies.pop(tenant_id, None)
        _cached_timestamp.pop(tenant_id, None)
    else:
        _cached_strategies.clear()
        _cached_timestamp.clear()

def load_strategy_code(strategy_name: str) -> str:
    file_path = STRATEGY_DIR / f"{strategy_name}.py"
    if not file_path.exists():
        return f"# 文件不存在: {file_path}"
    return file_path.read_text(encoding="utf-8")


def save_strategy_code(strategy_name: str, code: str, tenant_id: Optional[str] = None):
    file_path = STRATEGY_DIR / f"{strategy_name}.py"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code)
    
    tenant = tenant_id or get_current_tenant()
    
    # 从代码中提取DEFAULT_PARAMS并更新到数据库
    try:
        # 使用更可靠的字符串处理方法提取DEFAULT_PARAMS
        params_start = code.find('DEFAULT_PARAMS = {')
        if params_start != -1:
            # 找到起始位置后的第一个左花括号
            brace_start = code.find('{', params_start)
            if brace_start != -1:
                # 计算匹配的右花括号位置
                brace_count = 1
                params_str = '{'
                i = brace_start + 1
                while i < len(code) and brace_count > 0:
                    if code[i] == '{':
                        brace_count += 1
                    elif code[i] == '}':
                        brace_count -= 1
                    params_str += code[i]
                    i += 1
                
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
                
                # 2. 处理Python风格的None值 (None -> null)
                json_friendly_str = json_friendly_str.replace('None', 'null')
                
                # 3. 处理末尾多余的逗号
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
                        text("UPDATE sys_strategies SET params = :params WHERE name = :name AND tenant_id = :tenant_id"),
                        {
                            'tenant_id': tenant,
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
                                text("INSERT INTO sys_strategies (tenant_id, name, description, params) VALUES (:tenant_id, :name, '', :params)"),
                                {'tenant_id': tenant, 'name': strategy_name, 'params': params_json}
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
    
    clear_strategies_cache(tenant)
    return {"status": "ok", "path": str(file_path)}


def create_strategy(strategy_name: str, description: str = "", params: str = "{}", tenant_id: Optional[str] = None):
    file_path = STRATEGY_DIR / f"{strategy_name}.py"
    if file_path.exists():
        return {"status":"exists", "path": str(file_path)}
    
    tenant = tenant_id or get_current_tenant()
    
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
                text("INSERT INTO sys_strategies (tenant_id, name, description, params) VALUES (:tenant_id, :name, :description, :params)"),
                {
                    'tenant_id': tenant,
                    'name': strategy_name,
                    'description': description,
                    'params': params_json
                }
            )
            conn.commit()
    except Exception as e:
        print(f"警告: 数据库记录插入失败 - {e}")
    
    clear_strategies_cache(tenant)
        
    return {"status":"ok", "path": str(file_path)}

def delete_strategy(strategy_name: str, tenant_id: Optional[str] = None):
    file_path = STRATEGY_DIR / f"{strategy_name}.py"
    file_deleted = False
    db_deleted = False
    tenant = tenant_id or get_current_tenant()
    
    # 删除文件
    if file_path.exists():
        file_path.unlink()
        file_deleted = True
    
    # 从数据库删除记录
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("DELETE FROM sys_strategies WHERE name = :name AND tenant_id = :tenant_id"),
                {'name': strategy_name, 'tenant_id': tenant}
            )
            conn.commit()
            if result.rowcount > 0:
                db_deleted = True
    except Exception as e:
        print(f"警告: 数据库记录删除失败 - {e}")
    
    # 根据删除结果返回不同状态
    if db_deleted:
        clear_strategies_cache(tenant)
    if file_deleted and db_deleted:
        return {"status":"deleted", "path": str(file_path), "db":"deleted"}
    elif file_deleted:
        return {"status":"file_deleted", "path": str(file_path), "db":"not_found"}
    elif db_deleted:
        return {"status":"db_deleted", "path": str(file_path), "db":"deleted"}
    else:
        return {"status":"not_found"}
