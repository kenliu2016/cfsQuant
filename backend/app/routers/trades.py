from fastapi import APIRouter
from ..services.trades_service import get_trades_by_run_id

router = APIRouter(prefix="/api", tags=["trades"])

@router.get("/trades/{run_id}")
async def get_trades(run_id: str):
    """
    获取指定run_id的交易记录
    
    Args:
        run_id: 回测运行ID
        
    Returns:
        包含交易记录的JSON对象
    """
    df = get_trades_by_run_id(run_id)
    if df.empty:
        return {"rows": [], "message": "No trades found for this run_id"}
    return {"rows": df.to_dict(orient="records")}