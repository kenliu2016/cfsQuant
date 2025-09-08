from fastapi import APIRouter
from ..services.backtest_service import run_backtest, get_backtest_result
router = APIRouter(prefix="/api", tags=["backtest"])
@router.post("/backtest")
async def backtest(req: dict):
    backtest_id = run_backtest(req.get("code"), req.get("start"), req.get("end"), req.get("strategy"), req.get("params", {}))
    return {"backtest_id": backtest_id, "status":"finished"}

@router.get("/backtest/{backtest_id}/results")
async def backtest_results(backtest_id: str):
    return get_backtest_result(backtest_id) or {"error":"not_found"}
