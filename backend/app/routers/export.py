from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import io, pandas as pd, sqlalchemy as sa
from common.db import engine
from ..main.config import settings
router = APIRouter(prefix="/api", tags=["export"])
@router.get("/runs/{run_id}/export/csv")
async def export_csv(run_id: str, kind: str = "equity", request: Request = None):
    tenant_id = getattr(request.state, "tenant_id", settings.DEFAULT_TENANT_ID) if request else settings.DEFAULT_TENANT_ID
    with engine.connect() as conn:
        if kind == "metrics":
            df = pd.read_sql(sa.text("SELECT metric_name, metric_value FROM backtest_metrics WHERE run_id=:rid AND tenant_id=:tenant_id"), conn, params={"rid": run_id, "tenant_id": tenant_id})
        else:
            df = pd.read_sql(sa.text("SELECT datetime, nav, drawdown FROM backtest_equity_curve WHERE run_id=:rid AND tenant_id=:tenant_id ORDER BY datetime"), conn, params={"rid": run_id, "tenant_id": tenant_id})
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition":f"attachment; filename={run_id}-{kind}.csv"})
