"""AuthRouter — SSO mock/real + JWT (RF-28, ADR-06)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth_service import AuthService
from app.infrastructure.db import get_session
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.security import TokenError
from app.interface.deps import AuthError, CurrentUser, get_auth_service, get_current_user
from app.interface.schemas import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, service: AuthService = Depends(get_auth_service)
) -> dict:
    try:
        return await service.login(body.id_token)
    except TokenError as exc:
        raise AuthError("Credenciales inválidas") from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest, service: AuthService = Depends(get_auth_service)
) -> dict:
    try:
        return await service.refresh(body.refresh_token)
    except TokenError as exc:
        raise AuthError("Refresh token inválido o expirado") from exc


@router.get("/me", response_model=UserOut)
async def me(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stored = await UserRepository(session).get(user.id)
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": stored.full_name if stored else "",
        "role": user.role,
    }
