import uuid
from typing import Optional, Dict, Any
from datetime import datetime

import pandas as pd

from common.db import fetch_df, execute
from common import LoggerFactory
from ..main.security import hash_password, verify_password

logger = LoggerFactory.get_logger("auth_service")


def create_user(
    tenant_id: str,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    is_admin: bool = False,
    is_super_admin: bool = False,
) -> Dict[str, Any]:
    user_id = str(uuid.uuid4())
    hashed = hash_password(password)
    try:
        execute(
            """
            INSERT INTO tenant_users (id, tenant_id, email, hashed_password, full_name, is_admin, is_super_admin, is_active, created_at, updated_at)
            VALUES (:id, :tenant_id, :email, :hashed_password, :full_name, :is_admin, :is_super_admin, TRUE, NOW(), NOW())
            """,
            id=user_id,
            tenant_id=tenant_id,
            email=email.lower(),
            hashed_password=hashed,
            full_name=full_name,
            is_admin=is_admin,
            is_super_admin=is_super_admin,
        )
        logger.info("Created user %s for tenant %s", email, tenant_id)
        return get_user_by_id(user_id, tenant_id) or {}
    except Exception as exc:
        logger.error("Create user failed: %s", exc)
        raise ValueError("Unable to create user") from exc


def get_user_by_email(email: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    df = fetch_df(
        """
        SELECT id, tenant_id, email, hashed_password, full_name, is_admin, is_super_admin, is_active
        FROM tenant_users
        WHERE tenant_id = :tenant_id AND email = :email
        """,
        tenant_id=tenant_id,
        email=email.lower(),
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_user_by_id(user_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    df = fetch_df(
        """
        SELECT id, tenant_id, email, hashed_password, full_name, is_admin, is_super_admin, is_active
        FROM tenant_users
        WHERE tenant_id = :tenant_id AND id = :id
        """,
        tenant_id=tenant_id,
        id=user_id,
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def authenticate_user(tenant_id: str, email: str, password: str) -> Optional[Dict[str, Any]]:
    user = get_user_by_email(email, tenant_id)
    if not user:
        return None
    if not user.get("is_active", True):
        return None
    if not verify_password(password, user.get("hashed_password", "")):
        return None
    return user


def serialize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    if not user:
        return {}
    data = {
        "id": user.get("id"),
        "tenant_id": user.get("tenant_id"),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "is_admin": user.get("is_admin", False),
        "is_super_admin": user.get("is_super_admin", False),
        "is_active": user.get("is_active", True),
    }
    return data


def list_users(tenant_id: str) -> pd.DataFrame:
    df = fetch_df(
        """
        SELECT id, tenant_id, email, full_name, is_admin, is_super_admin, is_active, created_at, updated_at
        FROM tenant_users
        WHERE tenant_id = :tenant_id
        ORDER BY created_at ASC
        """,
        tenant_id=tenant_id,
    )
    return df


def update_user(
    tenant_id: str,
    user_id: str,
    full_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_admin: Optional[bool] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    set_clauses = []
    params: Dict[str, Any] = {"tenant_id": tenant_id, "id": user_id}
    if full_name is not None:
        set_clauses.append("full_name = :full_name")
        params["full_name"] = full_name
    if is_active is not None:
        set_clauses.append("is_active = :is_active")
        params["is_active"] = is_active
    if is_admin is not None:
        set_clauses.append("is_admin = :is_admin")
        params["is_admin"] = is_admin
    if password:
        set_clauses.append("hashed_password = :hashed_password")
        params["hashed_password"] = hash_password(password)

    if not set_clauses:
        return get_user_by_id(user_id, tenant_id) or {}

    set_clauses.append("updated_at = :updated_at")
    params["updated_at"] = datetime.utcnow()

    execute(
        f"""
        UPDATE tenant_users
        SET {', '.join(set_clauses)}
        WHERE tenant_id = :tenant_id AND id = :id
        """,
        **params,
    )
    return get_user_by_id(user_id, tenant_id) or {}
