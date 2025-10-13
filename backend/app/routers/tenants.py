from fastapi import APIRouter, Body, HTTPException
from typing import Any, Dict, Optional

from ..services import tenant_service

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("")
async def list_tenants(active: Optional[bool] = True):
    """
    List tenants. `active` defaults to True but can be overridden to show all.
    """
    df = tenant_service.list_tenants(active_only=active if active is not None else False)
    return {"rows": df.to_dict(orient="records")}


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str):
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

    try:
        tenant = tenant_service.create_tenant(tenant_id, name, description, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return tenant


@router.patch("/{tenant_id}")
async def update_tenant(tenant_id: str, payload: Dict[str, Any] = Body(...)):
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
async def delete_tenant(tenant_id: str):
    if tenant_id == "public":
        raise HTTPException(status_code=400, detail="Default tenant cannot be deleted")
    try:
        tenant_service.delete_tenant(tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "deleted"}
