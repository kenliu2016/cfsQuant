from fastapi import APIRouter, Depends, Request, HTTPException, Query

from ..services.audit_service import list_logs
from ..main.dependencies import require_user, require_tenant_admin
from ..main.config import settings

router = APIRouter(prefix="/api/audit-logs", tags=["audit-logs"], dependencies=[Depends(require_user)])


@router.get("")
async def get_audit_logs(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    tenant_id: str = Query(None),
    current_user=Depends(require_tenant_admin),
):
    effective_tenant = tenant_id or current_user["tenant_id"]
    if tenant_id and not current_user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Only super administrators can view other tenants' logs")
    df = list_logs(effective_tenant, offset=offset, limit=limit)
    return {"rows": df.to_dict(orient="records"), "total": len(df)}
