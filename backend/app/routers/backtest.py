from fastapi import APIRouter
from ..services.backtest_service import run_backtest, get_backtest_result
from ..schemas import BacktestRequest, BacktestResp
router = APIRouter(prefix="/api", tags=["backtest"])
@router.post("/backtest", response_model=BacktestResp)
async def backtest(req: BacktestRequest):
    backtest_result = run_backtest(req.code, req.start, req.end, req.strategy, req.params)
    # 从结果中提取run_id作为backtest_id
    backtest_id = backtest_result["run_id"] if isinstance(backtest_result, dict) and "run_id" in backtest_result else str(backtest_result)
    return {"backtest_id": backtest_id, "status":"finished"}

@router.get("/backtest/{backtest_id}/results")
async def backtest_results(backtest_id: str):
    return get_backtest_result(backtest_id) or {"error":"not_found"}
