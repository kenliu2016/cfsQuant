from fastapi import APIRouter, Request, Depends, HTTPException
import pandas as pd
from ..services.backtest_service import run_backtest, get_backtest_result
from ..services.market_service import get_candles
from common.schemas import BacktestRequest, BacktestResp
from ..main.dependencies import require_user
router = APIRouter(prefix="/api", tags=["backtest"], dependencies=[Depends(require_user)])
@router.post("/backtest", response_model=BacktestResp)
async def backtest(req: BacktestRequest, request: Request):
    
    # 从params中获取所有需要的字段
    # 获取交易对代码
    symbol = req.params.get('symbol')
    start = req.params['start']
    end = req.params['end']
    timeframe = req.params['timeframe']
    # 打印完整的回测请求信息
    # print(f"Backtest request: symbol={symbol}, start={start}, end={end}, timeframe={timeframe}, strategy={req.strategy}")
    # 调用get_candles获取K线数据
    candles_result = get_candles(symbol, start, end, timeframe)
    
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
        
    # 调用重构后的run_backtest方法，使用req.params作为参数
    tenant_id = getattr(request.state, "tenant_id", None)
    current_user = getattr(request.state, "user", {}) or {}
    backtest_result = run_backtest(
        df,
        req.params,
        req.strategy,
        tenant_id=tenant_id,
        user_id=current_user.get("id"),
    )
    
    # 从结果中提取run_id作为backtest_id
    backtest_id = backtest_result["run_id"] if isinstance(backtest_result, dict) and "run_id" in backtest_result else str(backtest_result)
    
    # 直接从backtest_result获取已经格式化好的signals - 不再进行额外转换
    # 在backtest_service.py中已经确保signals符合Dashboard所需的格式
    signals = backtest_result.get("signals", [])
    
    # 获取网格级别数据 - 直接从结果中获取，不再通过auxiliary_data中间层
    grid_levels = backtest_result.get("grid_levels", [])
    
    return {
        "backtest_id": backtest_id,
        "status": "finished",
        "signals": signals,  # 直接透传格式化后的signals
        "grid_levels": grid_levels
    }

@router.get("/backtest/{backtest_id}/results")
async def backtest_results(backtest_id: str, request: Request):
    tenant_id = getattr(request.state, "tenant_id", None)
    current_user = getattr(request.state, "user", {}) or {}
    try:
        return get_backtest_result(backtest_id, tenant_id=tenant_id, current_user=current_user) or {"error":"not_found"}
    except PermissionError:
        raise HTTPException(status_code=403, detail="access denied")
    except ValueError:
        raise HTTPException(status_code=404, detail="not found")
