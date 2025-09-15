from fastapi import APIRouter, Query
from fastapi import APIRouter, Query
from ..services.market_service import get_predictions
router = APIRouter(prefix="/api", tags=["predictions"])
@router.get("/predictions")
def predictions(code: str = Query(...), start: str = Query(...), end: str = Query(...)):
    df = get_predictions(code, start, end)
    if "datetime" in df.columns:
        df["datetime"] = df["datetime"].astype(str)
    return {"rows": df.to_dict(orient="records")}
