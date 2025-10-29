"""
Dashboard优化API接口
基于物化视图提供高性能的dashboard数据查询
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

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


@router.get("/dashboard/vmr-series", response_model=Dict[str, Any])
async def get_vmr_series(
    timeframe: str = Query(..., description="时间框架: 30m, 1h, 4h, 1d, 3d"),
    symbols: str = Query(None, description="币种符号，多个用逗号分隔；不传递则自动获取watch=true且quotecurrency=USDT的币种"),
    limit: int = Query(100, description="返回的记录数量，默认100条"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取VMR时间序列数据
    
    根据时间框架和币种符号查询VMR时间序列数据
    
    Args:
        timeframe: 时间框架，支持30m, 1h, 4h, 1d, 3d
        symbols: 币种符号，多个用逗号分隔；不传递则自动获取watch=true且quotecurrency=USDT的币种
        limit: 返回的记录数量
        
    Returns:
        VMR时间序列数据，包含：
        - series: 各币种的VMR时间序列数据
        - metadata: 元数据信息
    """
    try:
        # 将逗号分隔的symbols字符串转换为列表，如果为空则传递None让服务层动态获取
        symbols_list = [s.strip() for s in symbols.split(',')] if symbols else None
        service = DashboardOptimizedService(db)
        result = await service.get_vmr_series(timeframe, symbols_list, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取VMR时间序列数据失败: {str(e)}")