from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
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
class BacktestSignal(BaseModel):
    datetime: str
    side: str
    price: float
    qty: float

    @validator('datetime', pre=True)
    def validate_datetime(cls, v):
        # 使用 pre=True 确保在字段类型验证前运行
        if hasattr(v, 'strftime'):
            # 如果是Timestamp或datetime对象，转换为字符串
            return v.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(v, str):
            # 如果已经是字符串，直接返回
            return v
        else:
            # 其他情况转换为字符串
            return str(v)

class GridLevel(BaseModel):
    name: str
    price: float

class BacktestResp(BaseModel):
    backtest_id: str
    status: str
    signals: List[BacktestSignal] = []
    grid_levels: List[GridLevel] = []  # 修改为GridLevel对象数组
class HealthResp(BaseModel):
    status: str
