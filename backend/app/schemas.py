from pydantic import BaseModel
from typing import List, Optional, Dict, Any
class Candle(BaseModel):
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float
class CandleResp(BaseModel):
    code: str
    candles: List[Candle]
class BacktestRequest(BaseModel):
    code: str
    start: str
    end: str
    strategy: str
    params: Dict[str, Any] = {}
class BacktestResp(BaseModel):
    backtest_id: str
    status: str
class HealthResp(BaseModel):
    status: str
