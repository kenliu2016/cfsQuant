#!/usr/bin/env python3
"""
CoinMarketCap市值数据采集脚本
用于获取加密货币的市值和价格数据
"""

import requests
import pandas as pd
import json
from datetime import datetime, timezone
import sys
import os
import time
import re

# 添加项目根目录到Python路径，以便能够导入common模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.logger import LoggerFactory
from common.db import get_engine, get_connection
from sqlalchemy import text

# 使用项目统一的日志工具
logger = LoggerFactory.get_logger("fetchdata.market_cap")

# === 配置信息 ===
# 使用CoinGecko API作为替代方案（免费且无需API密钥）
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# API请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json"
}

def fetch_coingecko_data():
    """
    使用CoinGecko API获取加密货币数据
    """
    try:
        logger.info("开始获取CoinGecko API数据")
        
        # 获取前100个加密货币的市场数据
        url = f"{COINGECKO_API_URL}/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': 100,
            'page': 1,
            'sparkline': False,
            'price_change_percentage': '1h,24h,7d'
        }
        
        # 添加重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=HEADERS, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"成功获取 {len(data)} 条加密货币数据")
                
                crypto_data = []
                for i, coin in enumerate(data):
                    crypto_data.append({
                        'crypto_id': coin['id'],
                        'name': coin['name'],
                        'symbol': coin['symbol'].upper(),
                        'price_usd': coin['current_price'],
                        'market_cap_usd': coin['market_cap'],
                        'volume_24h_usd': coin['total_volume'],
                        'rank': coin['market_cap_rank']
                    })
                
                return crypto_data
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"API请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 * (attempt + 1))  # 指数退避
        
        return []
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API请求失败: {e}")
        return []
    except Exception as e:
        logger.error(f"处理API数据时出错: {e}")
        return []

def parse_crypto_data(api_data):
    """解析CoinGecko API数据"""
    try:
        logger.info("开始解析API数据")
        
        crypto_data = []
        for coin in api_data:
            # 使用排名作为crypto_id，因为数据库中的crypto_id是整数类型
            crypto_info = {
                'crypto_id': coin['rank'],  # 使用排名作为ID
                'name': coin['name'],
                'symbol': coin['symbol'],
                'cmc_rank': coin['rank'],
                'price': coin['price_usd'],
                'market_cap': coin['market_cap_usd'],
                'volume_24h': coin['volume_24h_usd'],
                'data_timestamp': datetime.now(timezone.utc)
            }
            crypto_data.append(crypto_info)
        
        logger.info(f"成功解析 {len(crypto_data)} 条加密货币数据")
        return crypto_data
        
    except Exception as e:
        logger.error(f"解析API数据失败: {e}")
        return []

def parse_numeric_value(text):
    """解析数值文本，转换为数字"""
    if not text or text == '--':
        return None
    
    # 移除货币符号和逗号
    text = text.replace('$', '').replace(',', '')
    
    # 处理科学计数法
    if 'T' in text:
        return float(text.replace('T', '')) * 1e12
    elif 'B' in text:
        return float(text.replace('B', '')) * 1e9
    elif 'M' in text:
        return float(text.replace('M', '')) * 1e6
    elif 'K' in text:
        return float(text.replace('K', '')) * 1e3
    
    try:
        return float(text)
    except ValueError:
        return None

def parse_percentage(text):
    """解析百分比文本"""
    if not text or text == '--':
        return None
    
    # 移除百分号
    text = text.replace('%', '')
    
    try:
        return float(text)
    except ValueError:
        return None

def save_to_database(crypto_data):
    """
    将加密货币数据保存到数据库
    """
    if not crypto_data:
        logger.warning("没有数据需要保存")
        return
    
    try:
        # 获取数据库连接
        engine = get_engine()
        
        # 创建DataFrame
        df = pd.DataFrame(crypto_data)
        
        # 确保数据类型正确
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['market_cap'] = pd.to_numeric(df['market_cap'], errors='coerce')
        df['volume_24h'] = pd.to_numeric(df['volume_24h'], errors='coerce')
        df['cmc_rank'] = pd.to_numeric(df['cmc_rank'], errors='coerce').astype('Int64')
        
        # 删除无效数据
        df = df.dropna(subset=['crypto_id', 'name', 'price'])
        
        logger.info(f"准备保存 {len(df)} 条数据到数据库")
        
        # 保存到数据库
        with engine.connect() as conn:
            # 使用INSERT ... ON CONFLICT UPDATE语法
            for _, row in df.iterrows():
                insert_sql = text("""
                    INSERT INTO market_cap (
                        crypto_id, name, symbol, cmc_rank, market_cap, 
                        price, volume_24h, data_timestamp
                    ) VALUES (
                        :crypto_id, :name, :symbol, :cmc_rank, :market_cap,
                        :price, :volume_24h, :data_timestamp
                    )
                    ON CONFLICT (crypto_id, data_timestamp) 
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        symbol = EXCLUDED.symbol,
                        cmc_rank = EXCLUDED.cmc_rank,
                        market_cap = EXCLUDED.market_cap,
                        price = EXCLUDED.price,
                        volume_24h = EXCLUDED.volume_24h,
                        updated_at = CURRENT_TIMESTAMP
                """)
                
                conn.execute(insert_sql, {
                    'crypto_id': row['crypto_id'],
                    'name': row['name'],
                    'symbol': row['symbol'],
                    'cmc_rank': row['cmc_rank'],
                    'market_cap': row['market_cap'],
                    'price': row['price'],
                    'volume_24h': row['volume_24h'],
                    'data_timestamp': row['data_timestamp']
                })
            
            conn.commit()
        
        logger.info(f"成功保存 {len(df)} 条数据到market_cap表")
        
    except Exception as e:
        logger.error(f"保存数据到数据库时出错: {e}")
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

def main():
    """主函数"""
    logger.info("开始执行加密货币市值数据采集任务")
    
    # 检查网络连接
    if not check_network_connectivity():
        logger.warning("网络连接不可用，跳过市值数据采集")
        return
    
    try:
        # 获取API数据
        api_data = fetch_coingecko_data()
        if not api_data:
            logger.error("无法获取API数据")
            return
        
        # 解析数据
        crypto_data = parse_crypto_data(api_data)
        if not crypto_data:
            logger.warning("未解析到有效数据")
            return
        
        # 保存数据
        save_to_database(crypto_data)
        
        logger.info("加密货币市值数据采集任务完成")
        
    except Exception as e:
        logger.error(f"执行任务时发生错误: {e}")
        raise

if __name__ == "__main__":
    main()