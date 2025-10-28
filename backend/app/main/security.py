from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import bcrypt
from jose import jwt, JWTError

from .config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # 检查密码长度是否超过bcrypt限制
    if len(plain_password.encode('utf-8')) > 72:
        # 如果密码超过72字节，截断到72字节
        plain_password = plain_password[:72]
    
    # 直接使用bcrypt库进行密码验证
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        # 如果bcrypt验证失败，记录错误并返回False
        import logging
        logging.error(f"Password verification failed: {e}")
        return False


def hash_password(password: str) -> str:
    # 检查密码长度是否超过bcrypt限制
    if len(password.encode('utf-8')) > 72:
        # 如果密码超过72字节，截断到72字节
        password = password[:72]
    
    # 直接使用bcrypt库进行密码哈希
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(subject: str, tenant_id: str, expires_minutes: Optional[int] = None, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode: Dict[str, Any] = {"exp": expire, "sub": subject, "tenant_id": tenant_id}
    if extra_claims:
        to_encode.update(extra_claims)
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str, verify_exp: bool = True) -> Dict[str, Any]:
    """
    解码JWT令牌
    
    Args:
        token: JWT令牌字符串
        verify_exp: 是否验证令牌过期时间，默认为True
        
    Returns:
        解码后的令牌载荷
        
    Raises:
        ValueError: 令牌无效时抛出异常
    """
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": verify_exp}
        )
        return payload
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
