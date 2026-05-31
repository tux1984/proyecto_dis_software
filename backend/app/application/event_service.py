"""EventService — ciclo de vida del evento (RF-05/06/07/09/24/27/30).

Orquesta creación, edición, publicación (con generación de embedding para la
búsqueda semántica), aprobación institucional y cancelación. Aplica la máquina
de estados del dominio (State) y registra cada cambio en auditoría.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from opentelemetry import trace

from app.domain.entities import Event
from app.domain.errors import DomainError, ValidationError
from app.domain.ports.adapters import IEmbeddingAdapter
from app.domain.ports.repositories import IAuditLogRepository, IEventRepository
from app.domain.value_objects import Modality, RegistrationType
from app.infrastructure.cache import catalog_cache
from app.infrastructure.repositories.support_repository import SessionRepository

logger = logging.getLogger("pgea.events")
_tracer = trace.get_tracer("pgea.events")


class PermissionDeniedError(DomainError):
    code = "forbidden"


class EventService:
    def __init__(
        self,
        events: IEventRepository,
        audit: IAuditLogRepository,
        embedding: IEmbeddingAdapter,
        sessions: SessionRepository,
        notifier=None,  # NotificationService (opcional, para cancelaciones)
    ) -> None:
        self._events = events
        self._audit = audit
        self._embedding = embedding
        self._sessions = sessions
        self._notifier = notifier

    async def create(self, organizer_id: UUID, data: dict) -> Event:
        event = Event(
            id=__import__("uuid").uuid4(),
            title=data["title"],
            description=data.get("description", ""),
            modality=Modality(data["modality"]),
            starts_at=data["starts_at"],
            ends_at=data["ends_at"],
            capacity=int(data["capacity"]),
            organizer_id=organizer_id,
            registration_type=RegistrationType(data.get("registration_type", "gratuita")),
            location=data.get("location"),
            external_url=data.get("external_url"),
            category_id=data.get("category_id"),
        )  # __post_init__ valida fechas y capacidad (ValidationError)
        await self._events.add(event)
        await self._audit.append(
            actor_user_id=organizer_id, action="event_created",
            entity_type="event", entity_id=event.id,
        )
        catalog_cache.invalidate()
        return event

    async def get(self, event_id: UUID) -> Event | None:
        return await self._events.get(event_id)

    async def list_by_organizer(self, organizer_id: UUID) -> list[Event]:
        return await self._events.list_by_organizer(organizer_id)

    async def update(self, event_id: UUID, actor_id: UUID, is_admin: bool, data: dict) -> Event:
        event = await self._require_owner(event_id, actor_id, is_admin)
        for field in ("title", "description", "location", "external_url"):
            if field in data and data[field] is not None:
                setattr(event, field, data[field])
        if "modality" in data and data["modality"]:
            event.modality = Modality(data["modality"])
        if "registration_type" in data and data["registration_type"]:
            event.registration_type = RegistrationType(data["registration_type"])
        if "capacity" in data and data["capacity"]:
            event.capacity = int(data["capacity"])
        if "category_id" in data:
            event.category_id = data["category_id"]
        if "starts_at" in data and data["starts_at"]:
            event.starts_at = data["starts_at"]
        if "ends_at" in data and data["ends_at"]:
            event.ends_at = data["ends_at"]
        if event.ends_at <= event.starts_at:
            raise ValidationError("La fecha de fin debe ser posterior a la de inicio")
        await self._events.update(event)
        await self._audit.append(
            actor_user_id=actor_id, action="event_updated",
            entity_type="event", entity_id=event.id,
        )
        catalog_cache.invalidate()
        return event

    async def publish(
        self, event_id: UUID, actor_id: UUID, is_admin: bool, request_approval: bool
    ) -> Event:
        event = await self._require_owner(event_id, actor_id, is_admin)
        if request_approval:
            event.submit_for_approval()
            await self._events.update(event)
            await self._audit.append(
                actor_user_id=actor_id, action="event_submitted_for_approval",
                entity_type="event", entity_id=event.id,
            )
            return event
        event.publish()
        await self._generate_embedding(event)
        await self._events.update(event)
        await self._audit.append(
            actor_user_id=actor_id, action="event_published",
            entity_type="event", entity_id=event.id,
        )
        catalog_cache.invalidate()
        return event

    async def approve(self, event_id: UUID, admin_id: UUID, comment: str) -> Event:
        if len(comment) < 20:
            raise ValidationError("El comentario debe tener al menos 20 caracteres")
        event = await self._get_or_raise(event_id)
        event.approve()
        await self._generate_embedding(event)
        await self._events.update(event)
        await self._audit.append(
            actor_user_id=admin_id, action="event_approved",
            entity_type="event", entity_id=event.id,
        )
        catalog_cache.invalidate()
        return event

    async def reject(self, event_id: UUID, admin_id: UUID, comment: str) -> Event:
        if len(comment) < 20:
            raise ValidationError("El comentario debe tener al menos 20 caracteres")
        event = await self._get_or_raise(event_id)
        event.reject()
        await self._events.update(event)
        await self._audit.append(
            actor_user_id=admin_id, action="event_rejected",
            entity_type="event", entity_id=event.id,
        )
        return event

    async def cancel(self, event_id: UUID, actor_id: UUID, is_admin: bool) -> Event:
        event = await self._require_owner(event_id, actor_id, is_admin)
        event.cancel()
        await self._events.update(event)
        await self._audit.append(
            actor_user_id=actor_id, action="event_cancelled",
            entity_type="event", entity_id=event.id,
        )
        if self._notifier is not None:
            await self._notifier.broadcast(
                event_id=event.id,
                actor_id=actor_id,
                subject=f"Evento cancelado: {event.title}",
                body=f"Lamentamos informar que el evento '{event.title}' ha sido cancelado.",
                segment="confirmed",
            )
        catalog_cache.invalidate()
        return event

    async def add_session(self, event_id: UUID, actor_id: UUID, is_admin: bool, data: dict) -> UUID:
        await self._require_owner(event_id, actor_id, is_admin)
        starts_at: datetime = data["starts_at"]
        ends_at: datetime = data["ends_at"]
        track = data.get("track")
        if await self._sessions.overlaps_in_track(event_id, track, starts_at, ends_at):
            raise ValidationError(
                f"Conflicto de horario en el track '{track}'"
            )
        return await self._sessions.add_session(
            event_id=event_id, title=data["title"], starts_at=starts_at,
            ends_at=ends_at, track=track, speaker_id=data.get("speaker_id"),
        )

    async def list_sessions(self, event_id: UUID) -> list[dict]:
        return await self._sessions.list_by_event(event_id)

    # -- helpers --
    async def _generate_embedding(self, event: Event) -> None:
        """Genera el embedding del evento al publicar (RF-30, ADR-07)."""
        try:
            with _tracer.start_as_current_span("event.generate_embedding"):
                text = f"{event.title}. {event.description}"
                vector = await self._embedding.embed(text)
                await self._events.set_embedding(event.id, vector)
        except Exception as exc:  # no bloquear la publicación por el embedding
            logger.warning("No se pudo generar embedding del evento %s: %s", event.id, exc)

    async def _get_or_raise(self, event_id: UUID) -> Event:
        event = await self._events.get(event_id)
        if event is None:
            raise ValidationError("Evento no encontrado")
        return event

    async def _require_owner(self, event_id: UUID, actor_id: UUID, is_admin: bool) -> Event:
        event = await self._get_or_raise(event_id)
        if not is_admin and event.organizer_id != actor_id:
            raise PermissionDeniedError("Solo el organizador dueño puede modificar el evento")
        return event
