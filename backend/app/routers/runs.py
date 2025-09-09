from fastapi import APIRouter
from ..services.runs_service import recent_runs, run_detail
router = APIRouter(prefix="/api", tags=["runs"])
@router.get("/runs")
async def runs(limit: int = 20):
    df = recent_runs(limit)
    return {"rows": df.to_dict(orient="records")}
@router.get("/runs/{run_id}")
async def runs_detail(run_id: str):
    # 现在run_detail函数直接返回包含四部分数据的字典
    detail_data = run_detail(run_id)
    return detail_data
