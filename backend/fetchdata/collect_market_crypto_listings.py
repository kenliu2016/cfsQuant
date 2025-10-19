import requests
import pandas as pd
import json
from datetime import datetime, timezone
import sys
import os

# 添加项目根目录到Python路径，以便能够导入common模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.logger import LoggerFactory
from common.db import get_engine, get_connection
from sqlalchemy import text

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("fetchdata.market_crypto_listings")

# === API 配置 ===
API_KEY = "aa933896-7789-4070-adf4-7a4231aa9e83"
API_BASE = "https://pro-api.coinmarketcap.com/v1/cryptocurrency"


def get_cmc_listings(limit=200, start=1, convert="USD"):
    """获取加密货币列表数据"""
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": API_KEY
    }
    
    params = {
        "limit": limit,
        "start": start,
        "convert": convert
    }
    
    url = f"{API_BASE}/listings/latest"
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # 检查API返回状态
        status = data.get("status", {})
        if status.get("error_code", 0) != 0:
            raise Exception(f"API error: {status.get('error_message', 'Unknown error')}")
        
        return data.get("data", [])
        
    except Exception as e:
        logger.error(f"获取CMC列表数据失败: {e}")
        raise


def parse_crypto_data(data):
    """解析加密货币数据为数据库插入格式"""
    parsed_records = []
    
    for crypto in data:
        try:
            # 基本信息
            crypto_id = crypto.get("id")
            name = crypto.get("name")
            symbol = crypto.get("symbol")
            slug = crypto.get("slug")
            cmc_rank = crypto.get("cmc_rank")
            
            # 供应信息
            circulating_supply = crypto.get("circulating_supply")
            total_supply = crypto.get("total_supply")
            max_supply = crypto.get("max_supply")
            infinite_supply = crypto.get("infinite_supply", False)
            
            # 时间信息
            last_updated_str = crypto.get("last_updated")
            date_added_str = crypto.get("date_added")
            
            # 转换时间格式
            last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00")) if last_updated_str else None
            date_added = datetime.fromisoformat(date_added_str.replace("Z", "+00:00")) if date_added_str else None
            
            # 标签信息（转换为JSON格式以匹配数据库JSONB类型）
            tags_list = crypto.get("tags", [])
            tags = json.dumps(tags_list) if tags_list else None
            
            # 价格信息
            quote = crypto.get("quote", {})
            usd_quote = quote.get("USD", {})
            
            price = usd_quote.get("price")
            volume_24h = usd_quote.get("volume_24h")
            volume_change_24h = usd_quote.get("volume_change_24h")
            percent_change_1h = usd_quote.get("percent_change_1h")
            percent_change_24h = usd_quote.get("percent_change_24h")
            percent_change_7d = usd_quote.get("percent_change_7d")
            market_cap = usd_quote.get("market_cap")
            market_cap_dominance = usd_quote.get("market_cap_dominance")
            fully_diluted_market_cap = usd_quote.get("fully_diluted_market_cap")
            quote_last_updated_str = usd_quote.get("last_updated")
            quote_last_updated = datetime.fromisoformat(quote_last_updated_str.replace("Z", "+00:00")) if quote_last_updated_str else None
            
            parsed_records.append({
                "crypto_id": crypto_id,
                "name": name,
                "symbol": symbol,
                "slug": slug,
                "cmc_rank": cmc_rank,
                "circulating_supply": circulating_supply,
                "total_supply": total_supply,
                "max_supply": max_supply,
                "infinite_supply": infinite_supply,
                "last_updated": last_updated,
                "date_added": date_added,
                "tags": tags,
                "price": price,
                "volume_24h": volume_24h,
                "volume_change_24h": volume_change_24h,
                "percent_change_1h": percent_change_1h,
                "percent_change_24h": percent_change_24h,
                "percent_change_7d": percent_change_7d,
                "market_cap": market_cap,
                "market_cap_dominance": market_cap_dominance,
                "fully_diluted_market_cap": fully_diluted_market_cap,
                "quote_last_updated": quote_last_updated,
                "data_timestamp": datetime.now(timezone.utc)
            })
            
        except Exception as e:
            logger.warning(f"解析加密货币数据失败 {crypto.get('symbol', 'Unknown')}: {e}")
            continue
    
    return parsed_records


def save_crypto_data(records):
    """保存加密货币数据到数据库"""
    if not records:
        logger.warning("无可保存的加密货币数据")
        return

    try:
        # 使用统一的数据库连接
        engine = get_engine()
        
        with engine.connect() as conn:
            # 使用executemany进行批量插入
            sql = text("""
                INSERT INTO market_crypto_listings (
                    crypto_id, name, symbol, slug, cmc_rank, 
                    circulating_supply, total_supply, max_supply, infinite_supply,
                    last_updated, date_added, tags, price, volume_24h, volume_change_24h,
                    percent_change_1h, percent_change_24h, percent_change_7d,
                    market_cap, market_cap_dominance, fully_diluted_market_cap,
                    quote_last_updated, data_timestamp
                ) VALUES (
                    :crypto_id, :name, :symbol, :slug, :cmc_rank,
                    :circulating_supply, :total_supply, :max_supply, :infinite_supply,
                    :last_updated, :date_added, :tags, :price, :volume_24h, :volume_change_24h,
                    :percent_change_1h, :percent_change_24h, :percent_change_7d,
                    :market_cap, :market_cap_dominance, :fully_diluted_market_cap,
                    :quote_last_updated, :data_timestamp
                )
                ON CONFLICT (crypto_id, symbol)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    slug = EXCLUDED.slug,
                    cmc_rank = EXCLUDED.cmc_rank,
                    circulating_supply = EXCLUDED.circulating_supply,
                    total_supply = EXCLUDED.total_supply,
                    max_supply = EXCLUDED.max_supply,
                    infinite_supply = EXCLUDED.infinite_supply,
                    last_updated = EXCLUDED.last_updated,
                    date_added = EXCLUDED.date_added,
                    tags = EXCLUDED.tags,
                    price = EXCLUDED.price,
                    volume_24h = EXCLUDED.volume_24h,
                    volume_change_24h = EXCLUDED.volume_change_24h,
                    percent_change_1h = EXCLUDED.percent_change_1h,
                    percent_change_24h = EXCLUDED.percent_change_24h,
                    percent_change_7d = EXCLUDED.percent_change_7d,
                    market_cap = EXCLUDED.market_cap,
                    market_cap_dominance = EXCLUDED.market_cap_dominance,
                    fully_diluted_market_cap = EXCLUDED.fully_diluted_market_cap,
                    quote_last_updated = EXCLUDED.quote_last_updated,
                    data_timestamp = EXCLUDED.data_timestamp,
                    updated_at = now()
            """)
            
            conn.execute(sql, records)
            conn.commit()
            
        logger.info(f"成功保存 {len(records)} 条加密货币记录")
        
    except Exception as e:
        logger.error(f"保存加密货币数据到数据库时出错: {e}")
        raise


def fetch_cmc_listings(limit=100):
    """获取并保存CMC加密货币列表"""
    logger.info(f"开始获取CMC加密货币列表，限制: {limit}")
    
    try:
        # 获取数据
        crypto_data = get_cmc_listings(limit=limit)
        
        # 解析数据
        parsed_data = parse_crypto_data(crypto_data)
        
        # 保存数据
        save_crypto_data(parsed_data)
        
        logger.info("CMC加密货币列表获取完成")
        
    except Exception as e:
        logger.error(f"获取CMC加密货币列表失败: {e}")
        raise


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
        logger.warning("网络连接不可用，跳过CMC加密货币列表采集")
        logger.info("任务完成（网络不可用模式）")
    else:
        try:
            # 获取前100个加密货币数据
            fetch_cmc_listings(limit=100)
            logger.info("CMC加密货币列表采集任务完成")
        except Exception as e:
            logger.error(f"CMC加密货币列表采集出错: {e}")