from datetime import timedelta
from fastapi import APIRouter, Body, HTTPException, Depends, Request

from ..services import auth_service
from ..services.tenant_service import get_tenant
from ..main.security import create_access_token
from ..main.config import settings
from ..main.dependencies import require_user, require_user_or_refresh_token, require_tenant_admin

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def register_user(payload: dict = Body(...), current_user=Depends(require_tenant_admin)):
    tenant_id = current_user["tenant_id"]
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Only administrators can create users")
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


@router.post("/login")
async def login(payload: dict = Body(...)):
    tenant_id = payload.get("tenant_id") or settings.DEFAULT_TENANT_ID
    email = payload.get("email")
    password = payload.get("password")

    if not tenant_id or not email or not password:
        raise HTTPException(status_code=400, detail="tenant_id, email and password are required")

    tenant = get_tenant(tenant_id)
    if not tenant or tenant.get("is_active") is False:
        raise HTTPException(status_code=403, detail="Tenant disabled or not found")

    user = auth_service.authenticate_user(tenant_id, email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    access_token = create_access_token(
        subject=str(user["id"]),  # 确保ID是字符串，避免UUID序列化问题
        tenant_id=tenant_id,
        extra_claims={
            "is_admin": user.get("is_admin", False),
            "is_super_admin": user.get("is_super_admin", False),
        },
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": auth_service.serialize_user(user),
        "tenant": tenant,
    }


@router.post("/refresh")
async def refresh_token(request: Request, current_user=Depends(require_user_or_refresh_token)):
    """
    刷新访问令牌
    
    Args:
        request: HTTP请求对象
        current_user: 当前用户信息
        
    Returns:
        新的访问令牌和相关信息
    """
    # 使用当前用户信息生成新的令牌
    access_token = create_access_token(
        subject=str(current_user["id"]),
        tenant_id=current_user["tenant_id"],
        extra_claims={
            "is_admin": current_user.get("is_admin", False),
            "is_super_admin": current_user.get("is_super_admin", False),
        },
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": auth_service.serialize_user(current_user),
        "tenant": request.state.tenant,
    }


@router.get("/me")
async def get_me(request: Request, current_user=Depends(require_user)):
    return {
        "user": auth_service.serialize_user(current_user),
        "tenant": request.state.tenant,
    }
