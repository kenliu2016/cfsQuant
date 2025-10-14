import json
from typing import Any, Dict, Optional
from datetime import datetime

import pandas as pd

from common.db import fetch_df, execute
from common import LoggerFactory
from .auth_service import create_user

logger = LoggerFactory.get_logger("tenant_service")


def list_tenants(active_only: bool = True) -> pd.DataFrame:
    """
    Retrieve tenants, optionally filtering by active flag.
    """
    sql = """
    SELECT tenant_id, name, description, is_active, settings, created_at, updated_at
    FROM tenants
    WHERE 1=1
    """
    params: Dict[str, Any] = {}
    if active_only:
        sql += " AND is_active = TRUE"

    sql += " ORDER BY created_at ASC"
    return fetch_df(sql, **params)


def get_tenant(tenant_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a single tenant record.
    """
    df = fetch_df(
        """
        SELECT tenant_id, name, description, is_active, settings, created_at, updated_at
        FROM tenants
        WHERE tenant_id = :tenant_id
        """,
        tenant_id=tenant_id,
    )
    if df.empty:
        return None
    record = df.iloc[0].to_dict()
    if isinstance(record.get("settings"), str):
        try:
            record["settings"] = json.loads(record["settings"])
        except json.JSONDecodeError:
            pass
    return record


def create_tenant(tenant_id: str, name: str, description: str = "", settings: Optional[Dict[str, Any]] = None,
                  admin_email: Optional[str] = None, admin_password: Optional[str] = None,
                  admin_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a tenant row.
    """
    logger.info("Creating tenant %s", tenant_id)
    existing = get_tenant(tenant_id)
    if existing:
        raise ValueError(f"Tenant '{tenant_id}' already exists")

    now = datetime.utcnow()
    execute(
        """
        INSERT INTO tenants (tenant_id, name, description, settings, created_at, updated_at)
        VALUES (:tenant_id, :name, :description, :settings, :created_at, :updated_at)
        """,
        tenant_id=tenant_id,
        name=name,
        description=description,
        settings=json.dumps(settings or {}),
        created_at=now,
        updated_at=now,
    )
    tenant = get_tenant(tenant_id) or {}

    if admin_email and admin_password:
        try:
            create_user(tenant_id, admin_email, admin_password, admin_name, is_admin=True)
        except Exception as exc:
            logger.error("Failed to create tenant admin: %s", exc)
            execute("DELETE FROM tenants WHERE tenant_id = :tenant_id", tenant_id=tenant_id)
            raise

    return tenant


def update_tenant(
    tenant_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update tenant metadata.
    """
    logger.info("Updating tenant %s", tenant_id)
    set_clauses = []
    params: Dict[str, Any] = {"tenant_id": tenant_id}

    if name is not None:
        set_clauses.append("name = :name")
        params["name"] = name
    if description is not None:
        set_clauses.append("description = :description")
        params["description"] = description
    if is_active is not None:
        set_clauses.append("is_active = :is_active")
        params["is_active"] = is_active
    if settings is not None:
        set_clauses.append("settings = :settings::jsonb")
        params["settings"] = json.dumps(settings)

    set_clauses.append("updated_at = :updated_at")
    params["updated_at"] = datetime.utcnow()

    if not set_clauses:
        # Nothing to update
        return get_tenant(tenant_id) or {}

    sql = f"""
    UPDATE tenants
    SET {', '.join(set_clauses)}
    WHERE tenant_id = :tenant_id
    """
    affected = execute(sql, **params)
    if affected == 0:
        raise ValueError(f"Tenant '{tenant_id}' not found")
    return get_tenant(tenant_id) or {}


def delete_tenant(tenant_id: str) -> None:
    """
    Hard delete tenant metadata.
    """
    logger.warning("Deleting tenant %s", tenant_id)
    affected = execute("DELETE FROM tenants WHERE tenant_id = :tenant_id", tenant_id=tenant_id)
    if affected == 0:
        raise ValueError(f"Tenant '{tenant_id}' not found")
