"""
Dashboard优化API接口
基于物化视图提供高性能的dashboard数据查询
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from common.db import get_async_session as get_db
from app.services.dashboard_optimized_service import DashboardOptimizedService

router = APIRouter()


@router.get("/dashboard/summary", response_model=Dict[str, Any])
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取dashboard汇总数据（优化版本）
    
    一次性返回所有dashboard需要的数据，减少HTTP请求开销
    
    Returns:
        dashboard汇总数据，包含：
        - strong_coins: 强势币种列表
        - weak_coins: 弱势币种列表  
        - coin_analysis: 币种分析表数据
        - market_sentiment: 市场情绪指标
        - last_updated: 数据更新时间
        - data_source: 数据来源标识
    """
    try:
        service = DashboardOptimizedService(db)
        result = await service.get_dashboard_summary_optimized()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取dashboard汇总数据失败: {str(e)}")