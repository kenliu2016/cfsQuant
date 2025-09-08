from fastapi import APIRouter
from ..services.runs_service import recent_runs, run_detail
router = APIRouter(prefix="/api", tags=["runs"])
@router.get("/runs")
async def runs(limit: int = 20):
    df = recent_runs(limit)
    return {"rows": df.to_dict(orient="records")}
@router.get("/runs/{run_id}")
async def runs_detail(run_id: str):
    df_m, df_e = run_detail(run_id)
    return {"metrics": df_m.to_dict(orient="records"), "equity": df_e.to_dict(orient="records")}
