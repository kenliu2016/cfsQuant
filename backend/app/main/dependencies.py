from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .security import decode_token
from .tenant_context import push_tenant, reset_tenant
from ..services.auth_service import get_user_by_id
from ..services.tenant_service import get_tenant
from .config import settings

security_scheme = HTTPBearer(auto_error=False)


async def require_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    token = credentials.credentials if credentials else None
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    user_id: str = payload.get("sub")
    tenant_id: str = payload.get("tenant_id", settings.DEFAULT_TENANT_ID)
    if not user_id or not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    
    user = get_user_by_id(user_id, tenant_id)
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")
    user.pop("hashed_password", None)
    
    # Ensure tenant exists/active
    tenant = get_tenant(tenant_id)
    if not tenant or tenant.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant disabled")
    
    # Seed tenant context for downstream handlers
    token_ctx = push_tenant(tenant_id)
    request.state.tenant_id = tenant_id
    request.state.user = user
    request.state.tenant = tenant
    request.state._tenant_token = token_ctx
    return user


async def cleanup_user(request: Request):
    token_ctx = getattr(request.state, "_tenant_token", None)
    if token_ctx is not None:
        reset_tenant(token_ctx)
