import time
from fastapi import Request
from common import LoggerFactory
from .config import settings
from .tenant_context import push_tenant, reset_tenant, get_current_tenant
from .security import decode_token

logger = LoggerFactory.get_logger("app.middleware")


async def tenant_middleware(request: Request, call_next):
    """
    Resolve tenant identifier from the incoming request and seed the context.
    """
    tenant_id = settings.DEFAULT_TENANT_ID
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
            tenant_id = payload.get("tenant_id", settings.DEFAULT_TENANT_ID)
        except ValueError:
            tenant_id = settings.DEFAULT_TENANT_ID
    else:
        tenant_id = (
            request.headers.get("X-Tenant-ID")
            or request.query_params.get("tenant_id")
            or settings.DEFAULT_TENANT_ID
        )
    request.state.tenant_id = tenant_id
    token = push_tenant(tenant_id)
    try:
        response = await call_next(request)
    finally:
        # Only reset the token that this middleware created
        # Do not reset tokens created by dependencies (like require_user)
        # as they have their own cleanup mechanisms
        reset_tenant(token)
    return response


async def logging_middleware(request: Request, call_next):
    """
    Basic HTTP request logging enriched with tenant information.
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    tenant_id = getattr(request.state, "tenant_id", get_current_tenant(settings.DEFAULT_TENANT_ID))
    logger.info(
        "[tenant=%s] %s %s - %s - %.4fs",
        tenant_id,
        request.method,
        request.url,
        response.status_code,
        process_time,
    )
    return response
