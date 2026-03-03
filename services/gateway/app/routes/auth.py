"""Auth routes — Login, refresh, logout, me."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth import (
    Role,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    get_current_user,
    verify_password,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes en secondes


class UserResponse(BaseModel):
    user_id: UUID
    username: str
    role: str


@router.post("/token", response_model=TokenResponse)
async def login(body: LoginRequest):
    """
    Authentification — retourne access_token + refresh_token.

    TODO: vérifier contre la table users en DB.
    Pour l'instant, utilisateurs de test hardcodés.
    """
    # TODO: remplacer par vérification DB
    test_users = {
        "admin": ("admin123", Role.ADMIN),
        "doctor": ("doctor123", Role.DOCTOR),
    }

    user_data = test_users.get(body.username)
    if not user_data or body.password != user_data[0]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
        )

    # TODO: récupérer le vrai user_id depuis DB
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    role = user_data[1]

    access_token = create_access_token(user_id, role)
    refresh_token = create_refresh_token(user_id)

    logger.info("auth.login_success", user_id=str(user_id), role=role.value)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: Annotated[TokenPayload, Depends(get_current_user)]):
    """Retourne le profil de l'utilisateur courant."""
    return UserResponse(
        user_id=user.user_id,
        username="TODO",  # récupérer depuis DB
        role=user.role.value,
    )


@router.post("/logout")
async def logout(user: Annotated[TokenPayload, Depends(get_current_user)]):
    """Logout — invalide le refresh token en DB."""
    # TODO: blacklister refresh token en Redis
    logger.info("auth.logout", user_id=str(user.user_id))
    return {"message": "Déconnecté avec succès"}
