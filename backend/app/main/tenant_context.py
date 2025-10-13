"""
Tenant context management utilities.

This module centralizes how the current tenant identifier is propagated
throughout the application. HTTP middleware is responsible for seeding the
context using request metadata (headers/query params). Background jobs or
other entrypoints can set the tenant explicitly by calling `push_tenant`.
"""

from contextvars import ContextVar
from typing import Optional

# Internal context variable that stores the active tenant identifier.
_tenant_ctx: ContextVar[str] = ContextVar("tenant_id", default="public")


def get_current_tenant(default: Optional[str] = None) -> str:
    """
    Return the tenant identifier bound to the current context.

    Args:
        default: Override value when context has not been seeded.

    Returns:
        Active tenant identifier string.
    """
    try:
        return _tenant_ctx.get()
    except LookupError:
        if default is not None:
            return default
        # Fallback to the ContextVar default
        return "public"


def push_tenant(tenant_id: str):
    """
    Bind the provided tenant identifier to the current execution context.

    Returns:
        Context token which must be used when resetting.
    """
    return _tenant_ctx.set(tenant_id)


def reset_tenant(token) -> None:
    """
    Reset the tenant context to the previous value using the provided token.
    """
    try:
        _tenant_ctx.reset(token)
    except LookupError:
        # Nothing to reset; ignore.
        pass
