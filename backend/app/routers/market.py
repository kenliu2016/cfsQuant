from fastapi import APIRouter, Query
from ..services.market_service import get_candles
router = APIRouter(prefix="/api/market", tags=["market"])
@router.get("/candles")
async def candles(code: str = Query(...), start: str = Query(...), end: str = Query(...), interval: str = Query("1m")):
    df = get_candles(code, start, end, interval)
    if "datetime" in df.columns:
        df["datetime"] = df["datetime"].astype(str)
    return {"rows": df.to_dict(orient="records")}


@router.get("/daily")
async def daily(code: str = Query(...), start: str = Query(...), end: str = Query(...)):
    from ..services.market_service import get_daily_candles
    df = get_daily_candles(code, start, end)
    if "datetime" in df.columns:
        df["datetime"] = df["datetime"].astype(str)
    return {"rows": df.to_dict(orient="records")}

@router.get("/intraday")
async def intraday(code: str = Query(...), start: str = Query(...), end: str = Query(...)):
    from ..services.market_service import get_intraday
    df = get_intraday(code, start, end)
    if "datetime" in df.columns:
        df["datetime"] = df["datetime"].astype(str)
    return {"rows": df.to_dict(orient="records")}
