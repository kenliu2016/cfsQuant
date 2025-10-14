import uuid
from typing import Any, Dict, Optional
from datetime import datetime

from common.db import execute, fetch_df
from common import LoggerFactory

logger = LoggerFactory.get_logger("audit_service")


def log_action(
    tenant_id: str,
    user_id: Optional[str],
    role: Optional[str],
    method: str,
    path: str,
    query: Optional[str],
    status_code: Optional[int],
    user_agent: Optional[str],
    ip_address: Optional[str],
    extra: Optional[Dict[str, Any]] = None,
):
    try:
        execute(
            """
            INSERT INTO tenant_audit_logs
            (id, tenant_id, user_id, role, method, path, query, status_code, user_agent, ip_address, created_at, extra)
            VALUES (:id, :tenant_id, :user_id, :role, :method, :path, :query, :status_code, :user_agent, :ip_address, :created_at, :extra::jsonb)
            """,
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            method=method,
            path=path,
            query=query,
            status_code=status_code,
            user_agent=user_agent,
            ip_address=ip_address,
            created_at=datetime.utcnow(),
            extra=extra or {},
        )
    except Exception as exc:
        logger.error("Failed to write audit log: %s", exc, exc_info=True)


def list_logs(tenant_id: str, offset: int = 0, limit: int = 100) -> Any:
    df = fetch_df(
        """
        SELECT id, tenant_id, user_id, role, method, path, query, status_code, user_agent, ip_address, created_at, extra
        FROM tenant_audit_logs
        WHERE tenant_id = :tenant_id
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )
    return df
