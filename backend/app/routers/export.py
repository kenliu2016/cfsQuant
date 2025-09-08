from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import io, pandas as pd, sqlalchemy as sa
from ..db import engine
router = APIRouter(prefix="/api", tags=["export"])
@router.get("/runs/{run_id}/export/csv")
async def export_csv(run_id: str, kind: str = "equity"):
    with engine.connect() as conn:
        if kind == "metrics":
            df = pd.read_sql(sa.text("SELECT metric_name, metric_value FROM metrics WHERE run_id=:rid"), conn, params={"rid": run_id})
        else:
            df = pd.read_sql(sa.text("SELECT datetime, nav, drawdown FROM equity_curve WHERE run_id=:rid ORDER BY datetime"), conn, params={"rid": run_id})
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition":f"attachment; filename={run_id}-{kind}.csv"})
