"""Auth — JWT, RBAC, password hashing."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from ryx_shared.config import RyxConfig

logger = structlog.get_logger(__name__)
config = RyxConfig()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()


class Role(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    VIEWER = "viewer"
    SYSTEM = "system"


class TokenPayload:
    def __init__(self, user_id: UUID, role: Role, exp: datetime):
        self.user_id = user_id
        self.role = role
        self.exp = exp


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: UUID, role: Role) -> str:
    expire = datetime.utcnow() + timedelta(minutes=config.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, config.jwt_secret_key, algorithm=config.jwt_algorithm)


def create_refresh_token(user_id: UUID) -> str:
    expire = datetime.utcnow() + timedelta(days=config.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, config.jwt_secret_key, algorithm=config.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> TokenPayload:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Token de type incorrect")

    return TokenPayload(
        user_id=UUID(payload["sub"]),
        role=Role(payload["role"]),
        exp=datetime.fromtimestamp(payload["exp"]),
    )


def require_role(*roles: Role):
    """Dependency factory pour RBAC."""
    async def _check(user: Annotated[TokenPayload, Depends(get_current_user)]):
        if user.role not in roles:
            logger.warning(
                "rbac.access_denied",
                user_id=str(user.user_id),
                required_roles=[r.value for r in roles],
                user_role=user.role.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle requis : {[r.value for r in roles]}",
            )
        return user
    return _check
