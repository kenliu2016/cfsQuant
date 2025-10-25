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
    symbol: str
    candles: List[Candle]
class BacktestRequest(BaseModel):
    strategy: str
    params: Dict[str, Any] = Field(
        ..., 
        example={"symbol": "BTCUSDT", "start": "2023-01-01", "end": "2023-01-02", "timeframe": "1m"}
    )

    @validator('params')
    def validate_params(cls, v):
        # 验证symbol字段
        if 'symbol' not in v:
            raise ValueError(f"Missing required field in params: 'symbol' is required")
        
        # 检查时间范围字段，支持'start'/'end'和'start_time'/'end_time'
        has_valid_start = 'start' in v or 'start_time' in v
        has_valid_end = 'end' in v or 'end_time' in v
        
        if not (has_valid_start and has_valid_end):
            raise ValueError(f"Missing required field in params: either 'start'/'end' or 'start_time'/'end_time' is required")
        
        # 检查timeframe字段
        if 'timeframe' not in v:
            raise ValueError(f"Missing required field in params: timeframe")
        
        # 如果只有start_time/end_time，将其复制到start/end，确保后续代码能正常工作
        if 'start_time' in v and 'start' not in v:
            v['start'] = v['start_time']
        if 'end_time' in v and 'end' not in v:
            v['end'] = v['end_time']
            
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
