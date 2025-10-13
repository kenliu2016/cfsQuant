from fastapi import APIRouter
from ..common import LoggerFactory, fetch_df

router = APIRouter()

# 初始化日志记录器
logger = LoggerFactory.get_logger("app.api.market")

@router.get("/api/market/data")
async def get_market_data():
    """
    获取市场数据接口示例
    """
    try:
        query = "SELECT * FROM market_data LIMIT 100"
        df = await fetch_df(query)
        return {"data": df.to_dict(orient="records")}
    except Exception as e:
        logger.error(f"获取市场数据失败: {e}")
        return {"error": str(e)}