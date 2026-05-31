"""Privacidad — Ley 1581 (RNF-10, RN-07).

El usuario consulta sus datos personales y solicita su supresión (anonimización
conservando trazabilidad). Cada acceso a PII queda auditado.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.privacy_service import PrivacyService
from app.interface.deps import CurrentUser, get_current_user, get_privacy_service

router = APIRouter(prefix="/me", tags=["privacy"])


@router.get("/data")
async def my_data(
    user: CurrentUser = Depends(get_current_user),
    service: PrivacyService = Depends(get_privacy_service),
) -> dict:
    return await service.get_my_data(user.id)


@router.delete("/data")
async def delete_my_data(
    user: CurrentUser = Depends(get_current_user),
    service: PrivacyService = Depends(get_privacy_service),
) -> dict:
    return await service.delete_my_data(user.id)
