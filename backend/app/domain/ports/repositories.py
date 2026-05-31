"""Puertos de persistencia (patrón Repository, SAD §9.1).

Abstraen el acceso a datos para que el dominio sea testeable sin BD real.
Las implementaciones (infraestructura) usan SQLAlchemy async + asyncpg y
comparten la sesión de la unidad de trabajo del request.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities import Enrollment, Event, User
from app.domain.value_objects import Modality, RegistrationStatus


@dataclass
class CatalogFilters:
    """Filtros combinables del catálogo (RF-01, RF-02)."""

    query: str | None = None
    category_id: UUID | None = None
    modality: Modality | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    sort: str = "date_asc"          # date_asc | date_desc | title


class IUserRepository(Protocol):
    async def add(self, user: User) -> None: ...
    async def get(self, user_id: UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def update(self, user: User) -> None: ...
    async def set_role(self, user_id: UUID, role: str) -> None: ...
    async def list_all(self) -> list[User]: ...


class IEventRepository(Protocol):
    async def add(self, event: Event) -> None: ...
    async def get(self, event_id: UUID) -> Event | None: ...
    async def update(self, event: Event) -> None: ...
    async def set_embedding(self, event_id: UUID, vector: list[float]) -> None: ...
    async def search_catalog(
        self, filters: CatalogFilters, limit: int, offset: int
    ) -> list[Event]:
        """Catálogo público (solo PUBLICADO) con filtros y full-text (RN-03)."""
        ...
    async def list_by_organizer(self, organizer_id: UUID) -> list[Event]: ...
    async def search_by_titles(
        self, fragments: list[str], filters: CatalogFilters, limit: int
    ) -> list[Event]: ...
    async def count_confirmed(self, event_id: UUID) -> int: ...


class IEnrollmentRepository(Protocol):
    async def reserve_capacity_and_create(
        self, event: Event, user_id: UUID, *, paid: bool, reserved_until: datetime | None,
        form_data: dict | None,
    ) -> Enrollment:
        """Operación crítica (RN-01, RNF-08): bloquea la fila del evento con
        ``SELECT … FOR UPDATE NO KEY``, recalcula el cupo con ``COUNT`` de
        confirmadas y crea la inscripción de forma atómica. Lanza
        ``NoCapacityError`` / ``DuplicateRegistrationError``.
        """
        ...

    async def get(self, enrollment_id: UUID) -> Enrollment | None: ...
    async def get_by_event_user(self, event_id: UUID, user_id: UUID) -> Enrollment | None: ...
    async def update(self, enrollment: Enrollment) -> None: ...
    async def list_by_event(
        self, event_id: UUID, status: RegistrationStatus | None = None
    ) -> list[Enrollment]: ...
    async def list_by_user(self, user_id: UUID) -> list[Enrollment]: ...
    async def list_by_user_with_events(self, user_id: UUID) -> list[dict]: ...
    async def list_expired_pending(self, now: datetime) -> list[Enrollment]: ...


class IAuditLogRepository(Protocol):
    async def append(
        self,
        *,
        actor_user_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID | None,
        result: str = "success",
        trace_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Inserta un registro de auditoría inmutable (RF-29, RN-07, ADR-10)."""
        ...

    async def query(
        self, *, action: str | None = None, actor_user_id: UUID | None = None, limit: int = 100
    ) -> list[dict]: ...


class IEmbeddingRepository(Protocol):
    async def semantic_search(
        self, query_vector: list[float], filters: CatalogFilters, limit: int
    ) -> list[Event]:
        """k vecinos más cercanos por similitud coseno (pgvector ``<=>``, RF-30)."""
        ...
