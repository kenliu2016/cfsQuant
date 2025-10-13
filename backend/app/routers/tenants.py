from fastapi import APIRouter, Body, HTTPException, Depends
from typing import Any, Dict, Optional

from ..services import tenant_service
from ..main.dependencies import require_user

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("")
async def list_tenants(active: Optional[bool] = True, current_user=Depends(require_user)):
    if not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Only administrators can list tenants")
    """
    List tenants. `active` defaults to True but can be overridden to show all.
    """
    df = tenant_service.list_tenants(active_only=active if active is not None else False)
    return {"rows": df.to_dict(orient="records")}


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, current_user=Depends(require_user)):
    if not current_user.get("is_admin", False) and tenant_id != current_user.get("tenant_id"):
        raise HTTPException(status_code=403, detail="Access denied")
    tenant = tenant_service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.post("")
async def create_tenant(payload: Dict[str, Any] = Body(...)):
    tenant_id = payload.get("tenant_id")
    name = payload.get("name")
    description = payload.get("description", "")
    settings = payload.get("settings")

    if not tenant_id or not name:
        raise HTTPException(status_code=400, detail="tenant_id and name are required")

    admin_email = payload.get("admin_email")
    admin_password = payload.get("admin_password")
    if not admin_email or not admin_password:
        raise HTTPException(status_code=400, detail="admin_email and admin_password are required to create a tenant")

    try:
        tenant = tenant_service.create_tenant(
            tenant_id,
            name,
            description,
            settings,
            admin_email=admin_email,
            admin_password=admin_password,
            admin_name=payload.get("admin_name"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return tenant


@router.patch("/{tenant_id}")
async def update_tenant(tenant_id: str, payload: Dict[str, Any] = Body(...), current_user=Depends(require_user)):
    if not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Only administrators can update tenants")
    if tenant_id == "public":
        # Allow updates but do not permit disabling the default tenant inadvertently.
        if payload.get("is_active") is False:
            raise HTTPException(status_code=400, detail="Default tenant cannot be deactivated")

    try:
        tenant = tenant_service.update_tenant(
            tenant_id,
            name=payload.get("name"),
            description=payload.get("description"),
            is_active=payload.get("is_active"),
            settings=payload.get("settings"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return tenant


@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str, current_user=Depends(require_user)):
    if not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Only administrators can delete tenants")
    if tenant_id == "public":
        raise HTTPException(status_code=400, detail="Default tenant cannot be deleted")
    try:
        tenant_service.delete_tenant(tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "deleted"}
