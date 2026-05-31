"""NotificationRouter — comunicaciones masivas asíncronas (RF-12, RN-08)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.notification_service import NotificationService
from app.domain.errors import ValidationError
from app.infrastructure.db import get_session
from app.infrastructure.repositories.event_repository import EventRepository
from app.interface.deps import (
    CurrentUser,
    ForbiddenError,
    get_notification_service,
    require_role,
)
from app.interface.schemas import BroadcastRequest

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/{event_id}/broadcast", status_code=202)
async def broadcast(
    event_id: UUID,
    body: BroadcastRequest,
    user: CurrentUser = Depends(require_role("organizer")),
    service: NotificationService = Depends(get_notification_service),
    session: AsyncSession = Depends(get_session),
) -> dict:
    event = await EventRepository(session).get(event_id)
    if event is None:
        raise ValidationError("Evento no encontrado")
    if user.role != "admin" and event.organizer_id != user.id:
        raise ForbiddenError("Solo el organizador dueño puede enviar comunicaciones")
    return await service.broadcast(
        event_id=event_id, actor_id=user.id,
        subject=body.subject, body=body.body, segment=body.segment,
    )


@router.get("/{notification_id}/status")
async def status(
    notification_id: UUID,
    user: CurrentUser = Depends(require_role("organizer")),
    service: NotificationService = Depends(get_notification_service),
) -> dict:
    return await service.status(notification_id)
