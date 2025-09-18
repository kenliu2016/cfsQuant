from fastapi import APIRouter
from ..services.backtest_service import run_backtest, get_backtest_result
from ..services.market_service import get_candles
from ..schemas import BacktestRequest, BacktestResp
router = APIRouter(prefix="/api", tags=["backtest"])
@router.post("/backtest", response_model=BacktestResp)
async def backtest(req: BacktestRequest):
    
    # 打印所有请求参数到终端
    print("run_backtest请求参数：", req.params)
    
    # 从params中获取所有需要的字段
    code = req.params['code']
    start = req.params['start']
    end = req.params['end']
    interval = req.params['interval']
    
    # 调用get_candles获取K线数据
    candles_result = get_candles(code, start, end, interval)
    
    # 根据返回值类型确定如何获取DataFrame
    if isinstance(candles_result, tuple):
        # 如果是元组，根据长度决定是两个值还是三个值的情况
        if len(candles_result) == 3:
            df, _, _ = candles_result
        else:
            df, _ = candles_result
    else:
        # 否则直接使用
        df = candles_result
       # 打印srategy参数到终端
    print("run_backtest请求参数：", req.strategy)
    print("run_backtest请求参数：", df.head())    # 调用重构后的run_backtest方法，使用req.params作为参数
    backtest_result = run_backtest(df, req.params, req.strategy)
    
    # 从结果中提取run_id作为backtest_id
    backtest_id = backtest_result["run_id"] if isinstance(backtest_result, dict) and "run_id" in backtest_result else str(backtest_result)
    return {"backtest_id": backtest_id, "status":"finished"}

@router.get("/backtest/{backtest_id}/results")
async def backtest_results(backtest_id: str):
    return get_backtest_result(backtest_id) or {"error":"not_found"}
