from fastapi import APIRouter, Request, Depends
from ..services.trades_service import get_trades_by_run_id
from ..main.dependencies import require_user

router = APIRouter(prefix="/api", tags=["trades"], dependencies=[Depends(require_user)])

@router.get("/trades/{run_id}")
async def get_trades(run_id: str, request: Request):
    """
    获取指定run_id的交易记录
    
    Args:
        run_id: 回测运行ID
        
    Returns:
        包含交易记录的JSON对象
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    df = get_trades_by_run_id(run_id, tenant_id=tenant_id)
    if df.empty:
        return {"rows": [], "message": "No trades found for this run_id"}
    return {"rows": df.to_dict(orient="records")}
