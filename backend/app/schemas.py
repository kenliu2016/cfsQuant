from pydantic import BaseModel, Field, validator
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
    strategy: str
    params: Dict[str, Any] = Field(
        ..., 
        example={"code": "BTCUSDT", "start": "2023-01-01", "end": "2023-01-02", "interval": "1m"}
    )

    @validator('params')
    def validate_params(cls, v):
        required_fields = ['code', 'start', 'end', 'interval']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Missing required field in params: {field}")
        return v
class BacktestResp(BaseModel):
    backtest_id: str
    status: str
class HealthResp(BaseModel):
    status: str
