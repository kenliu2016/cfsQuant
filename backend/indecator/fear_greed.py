import requests
import pandas as pd
from datetime import datetime, timezone
import sys
import os

# 添加项目根目录到Python路径，以便能够导入common模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.logger import LoggerFactory
from common.db import get_engine, get_connection
from sqlalchemy import text

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("indecator.fear_greed")

# === API 配置 ===
API_KEY = "aa933896-7789-4070-adf4-7a4231aa9e83"
API_BASE = "https://pro-api.coinmarketcap.com/v3/fear-and-greed"

# 备用数据源配置
ALTERNATIVE_API_URL = "https://api.alternative.me/fng/"


def try_alternative_source(endpoint: str, params: dict = None):
    """当主API不可用时，尝试使用备用数据源"""
    logger.info("尝试使用备用数据源获取恐惧贪婪指数...")
    
    try:
        # 备用API不需要API密钥，直接调用
        if endpoint == "latest":
            url = f"{ALTERNATIVE_API_URL}"
        elif endpoint == "historical":
            limit = params.get("limit", 100) if params else 100
            url = f"{ALTERNATIVE_API_URL}?limit={limit}"
        else:
            raise Exception(f"不支持的端点: {endpoint}")
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # 转换备用API格式为与CMC API兼容的格式
        if endpoint == "latest":
            # 备用API返回格式转换
            return {
                "data": [{
                    "timestamp": str(data.get("data", [{}])[0].get("timestamp", 0)),
                    "value": int(data.get("data", [{}])[0].get("value", 0)),
                    "value_classification": data.get("data", [{}])[0].get("value_classification", "Unknown")
                }]
            }
        elif endpoint == "historical":
            # 历史数据格式转换
            historical_data = data.get("data", [])
            converted_data = []
            for item in historical_data:
                converted_data.append({
                    "timestamp": str(item.get("timestamp", 0)),
                    "value": int(item.get("value", 0)),
                    "value_classification": item.get("value_classification", "Unknown")
                })
            return {"data": converted_data}
        
    except Exception as e:
        logger.error(f"备用数据源也失败: {e}")
        raise Exception(f"所有数据源均不可用: {e}")


def get_api_data(endpoint: str, params: dict = None, max_retries: int = 5):
    """通用函数：调用 CMC API，包含重试机制和更稳定的连接设置"""
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": API_KEY,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    url = f"{API_BASE}/{endpoint}"
    
    # 创建会话以复用连接
    session = requests.Session()
    
    # 添加重试机制
    for attempt in range(max_retries):
        try:
            # 使用更短的超时时间，但增加重试次数
            response = session.get(url, headers=headers, params=params or {}, 
                                 timeout=(10, 30),  # 连接超时10秒，读取超时30秒
                                 verify=True)
            response.raise_for_status()
            break  # 成功则退出重试循环
        except requests.exceptions.Timeout:
            logger.warning(f"API请求超时，第{attempt + 1}次重试...")
            if attempt == max_retries - 1:
                raise Exception("API请求超时，已达到最大重试次数")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"连接错误，第{attempt + 1}次重试...")
            if attempt == max_retries - 1:
                # 尝试备用数据源
                return try_alternative_source(endpoint, params)
        except requests.exceptions.RequestException as e:
            logger.warning(f"请求异常，第{attempt + 1}次重试...")
            if attempt == max_retries - 1:
                raise Exception(f"请求异常: {e}")
        
        # 如果不是最后一次尝试，等待一段时间后重试
        if attempt < max_retries - 1:
            import time
            time.sleep(2 ** attempt)  # 指数退避策略

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
    """写入 PostgreSQL - 使用统一的数据库连接接口"""
    if not records:
        logger.warning("无可保存数据")
        return

    try:
        # 使用统一的数据库连接
        engine = get_engine()
        
        # 使用SQLAlchemy执行批量插入
        with engine.connect() as conn:
            # 使用executemany进行批量插入
            sql = text("""
                INSERT INTO indecator_fear_greed (timestamp, value, value_classification, source)
                VALUES (:timestamp, :value, :value_classification, :source)
                ON CONFLICT (timestamp)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    value_classification = EXCLUDED.value_classification,
                    source = EXCLUDED.source,
                    created_at = now()
            """)
            
            # 将记录转换为字典格式
            records_dict = [
                {
                    "timestamp": record[0],
                    "value": record[1],
                    "value_classification": record[2],
                    "source": record[3]
                }
                for record in records
            ]
            
            conn.execute(sql, records_dict)
            conn.commit()
            
        logger.info(f"成功保存恐惧贪婪指数 {len(records)} 条记录")
        
    except Exception as e:
        logger.error(f"保存数据到数据库时出错: {e}")
        raise

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

def check_network_connectivity():
    """检查网络连接状态"""
    try:
        import socket
        socket.setdefaulttimeout(5)
        socket.gethostbyname("google.com")
        return True
    except:
        return False

if __name__ == "__main__":
    # 检查网络连接
    if not check_network_connectivity():
        logger.warning("网络连接不可用，跳过恐惧贪婪指数采集")
        logger.info("任务完成（网络不可用模式）")
    else:
        try:
            fetch_latest()        # 获取最新指数
            fetch_historical(500) # 获取历史指数（可改为任意数量）
            logger.info("全部任务完成。")
        except Exception as e:
            logger.error(f"出错：{e}")