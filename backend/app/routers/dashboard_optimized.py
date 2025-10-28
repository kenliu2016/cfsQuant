"""
Dashboard优化API路由
"""

from fastapi import APIRouter
from app.api.endpoints import dashboard_optimized

router = APIRouter()

# 包含Dashboard优化API端点
router.include_router(dashboard_optimized.router, prefix="/api/v1", tags=["Dashboard优化接口"])