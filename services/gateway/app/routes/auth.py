"""Auth routes — Login, refresh, logout, me."""

import hashlib
from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    Role,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..database import get_db
from ..models.user import User, RefreshToken

logger = structlog.get_logger(__name__)
router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class UserResponse(BaseModel):
    user_id: UUID
    username: str
    role: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "doctor"
    email: str | None = None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/token", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authentification — retourne access_token + refresh_token."""
    user = await db.scalar(select(User).where(User.username == body.username))

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    role = Role(user.role)
    user_id = UUID(user.user_id)
    access_token = create_access_token(user_id, role)
    refresh_token = create_refresh_token(user_id)

    # Persister le refresh token (hashé, jamais en clair)
    from ryx_shared.config import RyxConfig
    config = RyxConfig()
    expires_at = datetime.utcnow() + timedelta(days=config.jwt_refresh_token_expire_days)
    rt = RefreshToken(
        token_id=str(uuid4()),
        user_id=user.user_id,
        token_hash=_token_hash(refresh_token),
        expires_at=expires_at,
    )
    db.add(rt)
    await db.commit()

    logger.info("auth.login_success", user_id=user.user_id, role=role.value)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(body: dict, db: AsyncSession = Depends(get_db)):
    """Renouveler l'access token via refresh token."""
    token = body.get("refresh_token", "")
    if not token:
        raise HTTPException(status_code=400, detail="refresh_token manquant")

    try:
        payload = decode_token(token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Refresh token invalide")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token de type incorrect")

    token_hash = _token_hash(token)
    rt = await db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False))
    )
    if not rt or rt.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token expiré ou révoqué")

    user = await db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou désactivé")

    # Rotation : révoquer l'ancien, émettre un nouveau
    rt.revoked = True
    role = Role(user.role)
    user_id = UUID(user.user_id)
    new_access = create_access_token(user_id, role)
    new_refresh = create_refresh_token(user_id)

    from ryx_shared.config import RyxConfig
    config = RyxConfig()
    new_rt = RefreshToken(
        token_id=str(uuid4()),
        user_id=user.user_id,
        token_hash=_token_hash(new_refresh),
        expires_at=datetime.utcnow() + timedelta(days=config.jwt_refresh_token_expire_days),
    )
    db.add(new_rt)
    await db.commit()

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.get("/auth/me", response_model=UserResponse)
async def get_me(
    user: Annotated[TokenPayload, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """Retourne le profil de l'utilisateur courant."""
    row = await db.get(User, str(user.user_id))
    if not row:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return UserResponse(user_id=UUID(row.user_id), username=row.username, role=row.role)


@router.post("/auth/logout")
async def logout(
    user: Annotated[TokenPayload, Depends(get_current_user)],
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Logout — révoque le refresh token."""
    token = body.get("refresh_token", "")
    if token:
        token_hash = _token_hash(token)
        rt = await db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        if rt:
            rt.revoked = True
            await db.commit()

    logger.info("auth.logout", user_id=str(user.user_id))
    return {"message": "Déconnecté avec succès"}


@router.post("/auth/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
):
    """Créer un utilisateur. En production : protéger par require_role(Role.ADMIN)."""
    existing = await db.scalar(select(User).where(User.username == body.username))
    if existing:
        raise HTTPException(status_code=409, detail="Username déjà utilisé")

    user_id = str(uuid4())
    row = User(
        user_id=user_id,
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info("auth.user_created", user_id=user_id, username=body.username)
    return UserResponse(user_id=UUID(row.user_id), username=row.username, role=row.role)
