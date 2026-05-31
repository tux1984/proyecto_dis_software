"""EnrollmentRouter — inscripciones, webhook de pago y listado (RF-03/04/11/17)."""

from __future__ import annotations

import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.enrollment_service import EnrollmentService
from app.domain.errors import ValidationError
from app.infrastructure.db import get_session
from app.infrastructure.repositories.enrollment_repository import EnrollmentRepository
from app.infrastructure.repositories.event_repository import EventRepository
from app.interface.deps import (
    CurrentUser,
    ForbiddenError,
    get_current_user,
    get_enrollment_service,
    require_role,
)
from app.interface.schemas import EnrollRequest, PaymentWebhook

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


@router.post("/{event_id}/register", status_code=201)
async def register(
    event_id: UUID,
    body: EnrollRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    service: EnrollmentService = Depends(get_enrollment_service),
) -> dict:
    return_url = str(request.base_url).rstrip("/") + "/enrollments/confirm"
    return await service.register(event_id, user.id, body.form_data, return_url)


@router.post("/webhook")
async def payment_webhook(
    body: PaymentWebhook,
    x_signature: str | None = Header(default=None),
    service: EnrollmentService = Depends(get_enrollment_service),
) -> dict:
    # Endpoint público: lo invoca la pasarela. Idempotente (RN-06).
    return await service.handle_payment_webhook(body.model_dump(mode="json"), x_signature)


@router.post("/{enrollment_id}/cancel")
async def cancel(
    enrollment_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: EnrollmentService = Depends(get_enrollment_service),
) -> dict:
    return await service.cancel(enrollment_id, user.id)


@router.get("/mine")
async def my_enrollments(
    user: CurrentUser = Depends(get_current_user),
    service: EnrollmentService = Depends(get_enrollment_service),
) -> dict:
    return {"enrollments": await service.list_mine(user.id)}


@router.get("/event/{event_id}")
async def list_event_enrollments(
    event_id: UUID,
    search: str | None = None,
    user: CurrentUser = Depends(require_role("organizer")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _ensure_owner(session, event_id, user)
    rows = await EnrollmentRepository(session).list_with_users(event_id, search)
    return {"count": len(rows), "enrollments": rows}


@router.get("/event/{event_id}/export.csv")
async def export_csv(
    event_id: UUID,
    user: CurrentUser = Depends(require_role("organizer")),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    await _ensure_owner(session, event_id, user)
    rows = await EnrollmentRepository(session).list_with_users(event_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["full_name", "email", "status", "registered_at"])
    for r in rows:
        writer.writerow([r["full_name"], r["email"], r["status"], r["registered_at"]])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="inscritos-{event_id}.csv"'},
    )


async def _ensure_owner(session: AsyncSession, event_id: UUID, user: CurrentUser) -> None:
    event = await EventRepository(session).get(event_id)
    if event is None:
        raise ValidationError("Evento no encontrado")
    if user.role != "admin" and event.organizer_id != user.id:
        raise ForbiddenError("Solo el organizador dueño puede ver los inscritos")
