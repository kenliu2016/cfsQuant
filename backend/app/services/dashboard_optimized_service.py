"""
Dashboard优化服务模块
基于物化视图提供高性能的dashboard数据查询
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.main.config import settings
from common.db import get_async_session

logger = logging.getLogger(__name__)


class DashboardOptimizedService:
    """Dashboard优化服务类"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化Dashboard优化服务
        
        Args:
            db: 数据库会话对象
        """
        self.db = db
        
    async def get_strong_weak_coins_optimized(self) -> Dict[str, Any]:
        """
        获取强势弱势币种数据（优化版本）
        
        Returns:
            包含强势弱势币种数据的字典
        """
        try:
            # 使用新的物化视图查询强势弱势币种，包含复合分数
            query = text("""
                SELECT 
                    symbol,
                    current_price,
                    gain_24h as gain_24h_pct,
                    vmr_24h,
                    total_score as composite_score
                FROM dashboard_strong_weak_coins
                WHERE gain_24h IS NOT NULL
                ORDER BY gain_24h DESC
                LIMIT 20
            """)
            
            result = await self.db.execute(query)
            all_coins = result.fetchall()
            
            if not all_coins:
                logger.warning("物化视图中没有找到币种数据")
                return {"strong_coins": [], "weak_coins": []}
            
            # 分离强势和弱势币种
            strong_coins = []
            weak_coins = []
            
            for i, coin in enumerate(all_coins):
                # 获取小时数据用于缩略图
                hourly_data = await self._get_hourly_data_for_coin(coin.symbol)
                
                # 处理gain_24h_pct字段，如果为N/A则设置为0
                gain_24h_pct = coin.gain_24h_pct
                if gain_24h_pct == "N/A" or gain_24h_pct is None:
                    gain_24h_pct = 0.0
                else:
                    gain_24h_pct = float(gain_24h_pct)
                
                coin_data = {
                    "symbol": coin.symbol,
                    "current_price": float(coin.current_price) if coin.current_price else 0.0,
                    "gain_24h_pct": gain_24h_pct,
                    "gain_24h": gain_24h_pct,  # 添加gain_24h字段，与gain_24h_pct相同
                    "vmr_24h": float(coin.vmr_24h) if coin.vmr_24h else 0.0,
                    "composite_score": float(coin.composite_score) if coin.composite_score else 0.0,
                    "hourly_data": hourly_data
                }
                
                if i < 10:  # 前10个为强势币种
                    strong_coins.append(coin_data)
                else:  # 后10个为弱势币种
                    weak_coins.append(coin_data)
            
            logger.info(f"优化查询找到{len(strong_coins)}个强势币种和{len(weak_coins)}个弱势币种")
            
            return {
                "strong_coins": strong_coins,
                "weak_coins": weak_coins
            }
            
        except Exception as e:
            logger.error(f"获取强势弱势币种数据失败: {str(e)}")
            return {"strong_coins": [], "weak_coins": []}
    
    async def _get_hourly_data_for_coin(self, symbol: str) -> List[Dict[str, Any]]:
        """
        获取币种的小时数据用于缩略图显示
        
        Args:
            symbol: 币种符号
            
        Returns:
            小时数据列表
        """
        try:
            # 查询最近24小时的数据用于缩略图
            query = text("""
                SELECT 
                    close,
                    quote_volume,
                    bucket as timestamp
                FROM market_ohlcv_1h
                WHERE symbol = :symbol
                    AND bucket >= NOW() - INTERVAL '24 hours'
                ORDER BY bucket ASC
                LIMIT 24
            """)
            
            result = await self.db.execute(query, {"symbol": symbol})
            hourly_data = result.fetchall()
            
            formatted_data = []
            for data in hourly_data:
                formatted_data.append({
                    "close": float(data.close) if data.close else 0.0,
                    "quote_volume": float(data.quote_volume) if data.quote_volume else 0.0,
                    "timestamp": data.timestamp.isoformat() if data.timestamp else ""
                })
            
            return formatted_data
            
        except Exception as e:
            logger.warning(f"获取币种{symbol}的小时数据失败: {str(e)}")
            return []
    
    async def get_coin_analysis_table_optimized(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取币种分析表数据（优化版本）
        
        Args:
            limit: 返回记录数量限制
            
        Returns:
            币种分析表数据列表
        """
        try:
            # 使用新的物化视图查询币种分析数据
            query = text("""
                SELECT 
                    symbol,
                    current_price,
                    market_cap,
                    total_volume_24h as volume_24h,
                    vmr_24h as vmr,
                    ve_1h as ve_value,
                    composite_score
                FROM dashboard_coin_analysis
                ORDER BY composite_score DESC
                LIMIT :limit
            """)
            
            result = await self.db.execute(query, {"limit": limit})
            coins = result.fetchall()
            
            analysis_data = []
            for coin in coins:
                coin_data = {
                    "symbol": coin.symbol,
                    "current_price": float(coin.current_price) if coin.current_price else 0.0,
                    "market_cap": float(coin.market_cap) if coin.market_cap else 0.0,
                    "volume_24h": float(coin.volume_24h) if coin.volume_24h else 0.0,
                    "vmr": float(coin.vmr) if coin.vmr else 0.0,
                    "vmr_24h": float(coin.vmr) if coin.vmr else 0.0,  # 添加vmr_24h字段，与vmr相同
                    "ve_value": float(coin.ve_value) if coin.ve_value else 0.0,
                    "composite_score": float(coin.composite_score) if coin.composite_score else 0.0,
                    "rank": len(analysis_data) + 1
                }
                analysis_data.append(coin_data)
            
            logger.info(f"优化查询找到{len(analysis_data)}个币种分析数据")
            return analysis_data
            
        except Exception as e:
            logger.error(f"获取币种分析表数据失败: {str(e)}")
            return []
    
    async def get_market_sentiment_optimized(self) -> Dict[str, Any]:
        """
        获取市场情绪指标数据（优化版本）
        
        Returns:
            市场情绪指标数据字典
        """
        try:
            # 使用新的物化视图查询市场情绪数据
            query = text("""
                SELECT 
                    total_coins,
                    rising_coins,
                    falling_coins,
                    avg_gain_24h,
                    bull_bear_score,
                    fear_greed_index,
                    last_updated
                FROM dashboard_market_sentiment
                ORDER BY last_updated DESC
                LIMIT 1
            """)
            
            result = await self.db.execute(query)
            sentiment = result.fetchone()
            
            if not sentiment:
                return self._get_default_sentiment()
            
            sentiment_data = {
                "total_coins": sentiment.total_coins or 0,
                "rising_coins": sentiment.rising_coins or 0,
                "falling_coins": sentiment.falling_coins or 0,
                "avg_gain_24h": float(sentiment.avg_gain_24h) if sentiment.avg_gain_24h else 0.0,
                "bull_bear_score": float(sentiment.bull_bear_score) if sentiment.bull_bear_score else 0.0,
                "fear_greed_index": float(sentiment.fear_greed_index) if sentiment.fear_greed_index else 50.0,
                "last_updated": sentiment.last_updated.isoformat() if sentiment.last_updated else datetime.now().isoformat()
            }
            
            return sentiment_data
            
        except Exception as e:
            logger.error(f"获取市场情绪数据失败: {str(e)}")
            return self._get_default_sentiment()
    
    async def get_dashboard_summary_optimized(self) -> Dict[str, Any]:
        """
        获取dashboard汇总数据（优化版本）
        一次性返回所有dashboard需要的数据，减少HTTP请求
        
        Returns:
            dashboard汇总数据字典
        """
        try:
            # 并行获取所有数据
            strong_weak_coins = await self.get_strong_weak_coins_optimized()
            coin_analysis = await self.get_coin_analysis_table_optimized(300)
            market_sentiment = await self.get_market_sentiment_optimized()
            
            summary_data = {
                "strong_coins": strong_weak_coins.get("strong_coins", []),
                "weak_coins": strong_weak_coins.get("weak_coins", []),
                "coin_analysis": coin_analysis,
                "market_sentiment": market_sentiment,
                "last_updated": datetime.now().isoformat(),
                "data_source": "optimized_materialized_view"
            }
            
            logger.info("Dashboard汇总数据查询完成")
            return summary_data
            
        except Exception as e:
            logger.error(f"获取dashboard汇总数据失败: {str(e)}")
            return {
                "strong_coins": [],
                "weak_coins": [],
                "coin_analysis": [],
                "market_sentiment": self._get_default_sentiment(),
                "last_updated": datetime.now().isoformat(),
                "data_source": "fallback"
            }
    
    def _format_hourly_data(self, prices: List[float], volumes: List[float], timestamps: List[datetime]) -> List[Dict[str, Any]]:
        """
        格式化小时数据
        
        Args:
            prices: 价格列表
            volumes: 成交量列表
            timestamps: 时间戳列表
            
        Returns:
            格式化后的小时数据列表
        """
        if not prices or not volumes or not timestamps:
            return []
        
        hourly_data = []
        min_length = min(len(prices), len(volumes), len(timestamps))
        
        for i in range(min_length):
            data_point = {
                "close": float(prices[i]) if prices[i] else 0.0,
                "quote_volume": float(volumes[i]) if volumes[i] else 0.0,
                "timestamp": timestamps[i].isoformat() if hasattr(timestamps[i], 'isoformat') else str(timestamps[i])
            }
            hourly_data.append(data_point)
        
        return hourly_data
    
    def _get_default_sentiment(self) -> Dict[str, Any]:
        """
        获取默认的市场情绪数据
        
        Returns:
            默认市场情绪数据字典
        """
        return {
            "total_coins": 0,
            "rising_coins": 0,
            "falling_coins": 0,
            "avg_gain_24h": 0.0,
            "bull_bear_score": 0.0,
            "fear_greed_index": 50.0,
            "last_updated": datetime.now().isoformat()
        }


# 缓存管理器（可选，进一步提升性能）
class DashboardCacheManager:
    """Dashboard缓存管理器"""
    
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 300  # 5分钟缓存时间
    
    def get(self, key: str) -> Optional[Any]:
        """
        从缓存获取数据
        
        Args:
            key: 缓存键
            
        Returns:
            缓存数据或None
        """
        if key in self._cache:
            data, timestamp = self._cache[key]
            if (datetime.now() - timestamp).total_seconds() < self._cache_ttl:
                return data
            else:
                del self._cache[key]  # 清理过期缓存
        return None
    
    def set(self, key: str, data: Any) -> None:
        """
        设置缓存数据
        
        Args:
            key: 缓存键
            data: 缓存数据
        """
        self._cache[key] = (data, datetime.now())
    
    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()


# 全局缓存实例
dashboard_cache = DashboardCacheManager()