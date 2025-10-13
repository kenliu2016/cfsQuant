import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone
import sys
import os

# 添加项目根目录到Python路径，以便能够导入app模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.logger import LoggerFactory

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("indecator.fear_greed")

# ================== 数据库配置 ==================
DB_CONFIG = {
    "dbname": "quant",
    "user": "cfs",
    "password": "Cc563479,.",
    "host": "127.0.0.1",
    "port": 5432
}

# === API 配置 ===
API_KEY = "aa933896-7789-4070-adf4-7a4231aa9e83"
API_BASE = "https://pro-api.coinmarketcap.com/v3/fear-and-greed"


def get_api_data(endpoint: str, params: dict = None):
    """通用函数：调用 CMC API"""
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": API_KEY
    }

    url = f"{API_BASE}/{endpoint}"
    response = requests.get(url, headers=headers, params=params or {})
    response.raise_for_status()

    data = response.json()
    
    # 检查data是否为字典类型
    if not isinstance(data, dict):
        raise Exception(f"API返回的数据不是预期的字典格式，而是: {type(data)}")
    
    # 安全地获取status信息
    status = data.get("status", {})
    if isinstance(status, dict):
        error_code = status.get("error_code", 0)
        # 处理错误代码可能是字符串的情况
        try:
            error_code = int(error_code)
        except (ValueError, TypeError):
            pass
        
        if error_code != 0:
            raise Exception(f"API error: {status}")
    
    return data.get("data", [])



def parse_records(data):
    """解析 API 数据格式为数据库插入格式"""
    parsed = []
    
    # 检查data是否为列表
    if not isinstance(data, list):
        # 尝试转换为列表格式
        if isinstance(data, dict):
            data = [data]
        else:
            return []
    
    for item in data:
        # 确保item是字典类型
        if not isinstance(item, dict):
            continue
        
        try:
            # 处理Unix时间戳（整数形式的字符串）
            timestamp_str = item["timestamp"]
            if timestamp_str.isdigit():
                # 转换Unix时间戳（秒）到UTC时区的datetime对象
                # 使用utcfromtimestamp确保在所有Python版本中都兼容
                ts = datetime.utcfromtimestamp(int(timestamp_str))
            else:
                # 尝试解析ISO格式时间（确保转换为UTC时区）
                ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                
            parsed.append((
                ts,
                item["value"],
                item["value_classification"],
                "CMC"
            ))
        except (KeyError, TypeError, ValueError):
            continue
    
    return parsed


def save_to_postgres(records):
    """写入 PostgreSQL"""
    if not records:
        logger.warning("无可保存数据")
        return

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    sql = """
    INSERT INTO fear_greed_index (timestamp, value, value_classification, source)
    VALUES %s
    ON CONFLICT (timestamp)
    DO UPDATE SET
        value = EXCLUDED.value,
        value_classification = EXCLUDED.value_classification,
        source = EXCLUDED.source,
        created_at = now();
    """
    execute_values(cur, sql, records)
    conn.commit()
    logger.info(f"成功保存恐惧贪婪指数 {len(records)} 条记录")
    cur.close()
    conn.close()

def fetch_latest():
    """获取最新恐惧与贪婪指数"""
    logger.info("正在获取最新 Fear & Greed Index...")
    data = get_api_data("latest")
    records = parse_records(data)
    save_to_postgres(records)

def fetch_historical(limit=100):
    """获取历史恐惧与贪婪指数"""
    logger.info(f"正在获取最近 {limit} 条历史数据...")
    data = get_api_data("historical", params={"limit": limit})
    records = parse_records(data)
    save_to_postgres(records)

if __name__ == "__main__":
    try:
        fetch_latest()        # 获取最新指数
        fetch_historical(500) # 获取历史指数（可改为任意数量）
        logger.info("全部任务完成。")
    except Exception as e:
        logger.error(f"出错：{e}")