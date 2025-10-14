import uuid
from typing import Optional, Dict, Any

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
    user.pop("hashed_password", None)
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
