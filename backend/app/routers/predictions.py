from fastapi import APIRouter, Query
from ..services.market_service import get_predictions, aget_predictions
router = APIRouter(prefix="/api", tags=["predictions"])
@router.get("/predictions")
async def predictions(code: str = Query(...), start: str = Query(...), end: str = Query(...)):
    df = await aget_predictions(code, start, end)
    if "datetime" in df.columns:
        df["datetime"] = df["datetime"].astype(str)
    return {"rows": df.to_dict(orient="records")}
