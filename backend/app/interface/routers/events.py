"""EventRouter — catálogo y ciclo de vida del evento (RF-01/05/06/07/09/16/18/24)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import PlainTextResponse

from app.application.admin_service import AdminService
from app.application.event_service import EventService
from app.application.search_service import SearchService
from app.domain.errors import ValidationError
from app.domain.ports.repositories import CatalogFilters
from app.domain.value_objects import Modality
from app.interface.deps import (
    CurrentUser,
    ForbiddenError,
    get_admin_service,
    get_calendar_adapter,
    get_event_service,
    get_search_service,
    require_role,
)
from app.interface.schemas import (
    ApprovalRequest,
    EventCreate,
    EventUpdate,
    PublishRequest,
    SessionCreate,
)

router = APIRouter(prefix="/events", tags=["events"])


# ---- Catálogo (público) ----
@router.get("")
async def list_events(
    category_id: UUID | None = None,
    modality: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    sort: str = "date_asc",
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    service: SearchService = Depends(get_search_service),
) -> dict:
    filters = CatalogFilters(
        query=q,
        category_id=category_id,
        modality=Modality(modality) if modality else None,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
    )
    results = await service.search(filters, limit=limit, offset=offset)
    return {"count": len(results), "results": results}


@router.get("/mine")
async def my_events(
    user: CurrentUser = Depends(require_role("organizer")),
    service: EventService = Depends(get_event_service),
) -> dict:
    # Eventos del organizador (todos los estados, incluidos borradores).
    events = await service.list_by_organizer(user.id)
    return {
        "events": [
            {
                "id": str(e.id), "title": e.title, "status": e.status.value,
                "modality": e.modality.value, "capacity": e.capacity,
                "registration_type": e.registration_type.value,
                "starts_at": e.starts_at.isoformat(),
            }
            for e in events
        ]
    }


@router.get("/{event_id}")
async def get_event(
    event_id: UUID, service: EventService = Depends(get_event_service)
) -> dict:
    event = await service.get(event_id)
    if event is None:
        raise ValidationError("Evento no encontrado")
    return {
        "id": str(event.id),
        "title": event.title,
        "description": event.description,
        "modality": event.modality.value,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
        "location": event.location,
        "external_url": event.external_url,
        "capacity": event.capacity,
        "status": event.status.value,
        "registration_type": event.registration_type.value,
        "organizer_id": str(event.organizer_id),
        "sessions": await service.list_sessions(event_id),
    }


@router.get("/{event_id}/calendar.ics", response_class=PlainTextResponse)
async def export_ics(
    event_id: UUID,
    service: EventService = Depends(get_event_service),
    calendar=Depends(get_calendar_adapter),
) -> Response:
    event = await service.get(event_id)
    if event is None:
        raise ValidationError("Evento no encontrado")
    ics = calendar.build_ics(
        uid=str(event.id),
        title=event.title,
        description=event.description,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        location=event.location,
    )
    return PlainTextResponse(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="evento-{event_id}.ics"'},
    )


# ---- Gestión (organizador / admin) ----
@router.post("", status_code=201)
async def create_event(
    body: EventCreate,
    user: CurrentUser = Depends(require_role("organizer")),
    service: EventService = Depends(get_event_service),
) -> dict:
    event = await service.create(user.id, body.model_dump())
    return {"id": str(event.id), "status": event.status.value}


@router.patch("/{event_id}")
async def update_event(
    event_id: UUID,
    body: EventUpdate,
    user: CurrentUser = Depends(require_role("organizer")),
    service: EventService = Depends(get_event_service),
) -> dict:
    event = await service.update(
        event_id, user.id, user.role == "admin", body.model_dump(exclude_none=True)
    )
    return {"id": str(event.id), "status": event.status.value}


@router.post("/{event_id}/publish")
async def publish_event(
    event_id: UUID,
    body: PublishRequest,
    user: CurrentUser = Depends(require_role("organizer")),
    service: EventService = Depends(get_event_service),
) -> dict:
    event = await service.publish(event_id, user.id, user.role == "admin", body.request_approval)
    return {"id": str(event.id), "status": event.status.value}


@router.post("/{event_id}/cancel")
async def cancel_event(
    event_id: UUID,
    user: CurrentUser = Depends(require_role("organizer")),
    service: EventService = Depends(get_event_service),
) -> dict:
    event = await service.cancel(event_id, user.id, user.role == "admin")
    return {"id": str(event.id), "status": event.status.value}


@router.post("/{event_id}/approve")
async def approve_event(
    event_id: UUID,
    body: ApprovalRequest,
    user: CurrentUser = Depends(require_role("admin")),
    service: EventService = Depends(get_event_service),
) -> dict:
    event = await service.approve(event_id, user.id, body.comment)
    return {"id": str(event.id), "status": event.status.value}


@router.post("/{event_id}/reject")
async def reject_event(
    event_id: UUID,
    body: ApprovalRequest,
    user: CurrentUser = Depends(require_role("admin")),
    service: EventService = Depends(get_event_service),
) -> dict:
    event = await service.reject(event_id, user.id, body.comment)
    return {"id": str(event.id), "status": event.status.value}


@router.get("/{event_id}/dashboard")
async def event_dashboard(
    event_id: UUID,
    user: CurrentUser = Depends(require_role("organizer")),
    service: EventService = Depends(get_event_service),
    admin: AdminService = Depends(get_admin_service),
) -> dict:
    # Reportes del evento para el organizador dueño (RF-14).
    event = await service.get(event_id)
    if event is None:
        raise ValidationError("Evento no encontrado")
    if user.role != "admin" and event.organizer_id != user.id:
        raise ForbiddenError("Solo el organizador dueño puede ver los reportes")
    return await admin.event_dashboard(event_id)


@router.post("/{event_id}/sessions", status_code=201)
async def add_session(
    event_id: UUID,
    body: SessionCreate,
    user: CurrentUser = Depends(require_role("organizer")),
    service: EventService = Depends(get_event_service),
) -> dict:
    sid = await service.add_session(
        event_id, user.id, user.role == "admin", body.model_dump()
    )
    return {"id": str(sid)}
