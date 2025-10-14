from fastapi import APIRouter, Body, HTTPException, Depends, Query
from typing import Any, Dict, Optional

from ..services import auth_service
from ..main.dependencies import require_user, require_tenant_admin

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_user)])


@router.get("")
async def list_users(tenant_id: Optional[str] = Query(None), current_user=Depends(require_tenant_admin)):
    target_tenant = tenant_id or current_user["tenant_id"]
    if tenant_id and not current_user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Only super administrators can view other tenants")
    df = auth_service.list_users(target_tenant)
    return {"rows": df.to_dict(orient="records")}


@router.post("")
async def create_user(payload: Dict[str, Any] = Body(...), current_user=Depends(require_tenant_admin)):
    tenant_id = current_user["tenant_id"]
    email = payload.get("email")
    password = payload.get("password")
    full_name = payload.get("full_name")
    is_admin = payload.get("is_admin", False)
    is_super_admin = payload.get("is_super_admin", False)
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    if is_super_admin and not current_user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Only super administrators can create super administrators")
    try:
        user = auth_service.create_user(tenant_id, email, password, full_name, is_admin, is_super_admin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return auth_service.serialize_user(user)


@router.patch("/{user_id}")
async def update_user(user_id: str, payload: Dict[str, Any] = Body(...), current_user=Depends(require_tenant_admin)):
    tenant_id = current_user["tenant_id"]
    target_user = auth_service.get_user_by_id(user_id, tenant_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if target_user.get("is_super_admin") and not current_user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Cannot modify super administrator")

    updates: Dict[str, Any] = {}
    for field in ["full_name", "is_active", "is_admin", "password"]:
        if field in payload:
            updates[field] = payload[field]

    if not updates:
        return auth_service.serialize_user(target_user)

    user = auth_service.update_user(
        tenant_id=tenant_id,
        user_id=user_id,
        full_name=updates.get("full_name"),
        is_active=updates.get("is_active"),
        is_admin=updates.get("is_admin"),
        password=updates.get("password"),
    )
    return auth_service.serialize_user(user)
