"""Repositorio de eventos: catálogo, ciclo de vida y embedding (RF-01/02/05/30)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Event
from app.domain.ports.repositories import CatalogFilters
from app.domain.value_objects import EventStatus, RegistrationStatus
from app.infrastructure.models import EnrollmentModel, EventModel
from app.infrastructure.repositories.mappers import to_event


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, event: Event) -> None:
        self._s.add(
            EventModel(
                id=event.id,
                title=event.title,
                description=event.description,
                modality=event.modality.value,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                location=event.location,
                external_url=event.external_url,
                capacity=event.capacity,
                status=event.status.value,
                registration_type=event.registration_type.value,
                organizer_id=event.organizer_id,
                category_id=event.category_id,
                created_at=event.created_at,
                published_at=event.published_at,
            )
        )
        await self._s.flush()

    async def get(self, event_id: UUID) -> Event | None:
        m = await self._s.get(EventModel, event_id)
        return to_event(m) if m else None

    async def update(self, event: Event) -> None:
        m = await self._s.get(EventModel, event.id)
        if m is None:
            return
        m.title = event.title
        m.description = event.description
        m.modality = event.modality.value
        m.starts_at = event.starts_at
        m.ends_at = event.ends_at
        m.location = event.location
        m.external_url = event.external_url
        m.capacity = event.capacity
        m.status = event.status.value
        m.registration_type = event.registration_type.value
        m.category_id = event.category_id
        m.published_at = event.published_at
        await self._s.flush()

    async def set_embedding(self, event_id: UUID, vector: list[float]) -> None:
        m = await self._s.get(EventModel, event_id)
        if m is not None:
            m.embedding = vector
            await self._s.flush()

    async def search_catalog(
        self, filters: CatalogFilters, limit: int, offset: int
    ) -> list[Event]:
        # Solo eventos publicados son visibles en el catálogo (RN-03)
        stmt = select(EventModel).where(EventModel.status == EventStatus.PUBLICADO.value)

        if filters.category_id:
            stmt = stmt.where(EventModel.category_id == filters.category_id)
        if filters.modality:
            stmt = stmt.where(EventModel.modality == filters.modality.value)
        if filters.date_from:
            stmt = stmt.where(EventModel.starts_at >= filters.date_from)
        if filters.date_to:
            stmt = stmt.where(EventModel.starts_at <= filters.date_to)
        if filters.query:
            # Full-text en español (usa el índice GIN) + fallback ILIKE
            ts = func.to_tsvector(
                "spanish", EventModel.title + " " + EventModel.description
            )
            q = func.plainto_tsquery("spanish", filters.query)
            stmt = stmt.where(ts.op("@@")(q))

        # Orden (RF-02)
        if filters.sort == "date_desc":
            stmt = stmt.order_by(EventModel.starts_at.desc())
        elif filters.sort == "title":
            stmt = stmt.order_by(EventModel.title.asc())
        else:
            stmt = stmt.order_by(EventModel.starts_at.asc())

        stmt = stmt.limit(limit).offset(offset)
        res = await self._s.execute(stmt)
        return [to_event(m) for m in res.scalars().all()]

    async def search_by_titles(
        self, fragments: list[str], filters: CatalogFilters, limit: int
    ) -> list[Event]:
        """Eventos publicados cuyo título coincide con alguno de los fragmentos
        (búsqueda semántica curada, RF-30). Ordena por relevancia del fragmento.
        """
        from sqlalchemy import or_

        stmt = select(EventModel).where(EventModel.status == EventStatus.PUBLICADO.value)
        if filters.category_id:
            stmt = stmt.where(EventModel.category_id == filters.category_id)
        if filters.modality:
            stmt = stmt.where(EventModel.modality == filters.modality.value)
        if filters.date_from:
            stmt = stmt.where(EventModel.starts_at >= filters.date_from)
        if filters.date_to:
            stmt = stmt.where(EventModel.starts_at <= filters.date_to)
        stmt = stmt.where(or_(*[EventModel.title.ilike(f"%{f}%") for f in fragments]))

        res = await self._s.execute(stmt)
        events = [to_event(m) for m in res.scalars().all()]

        def _rank(ev: Event) -> int:
            title = ev.title.lower()
            for i, frag in enumerate(fragments):
                if frag.lower() in title:
                    return i
            return len(fragments)

        events.sort(key=_rank)
        return events[:limit]

    async def list_by_organizer(self, organizer_id: UUID) -> list[Event]:
        res = await self._s.execute(
            select(EventModel)
            .where(EventModel.organizer_id == organizer_id)
            .order_by(EventModel.created_at.desc())
        )
        return [to_event(m) for m in res.scalars().all()]

    async def count_confirmed(self, event_id: UUID) -> int:
        res = await self._s.execute(
            select(func.count())
            .select_from(EnrollmentModel)
            .where(
                EnrollmentModel.event_id == event_id,
                EnrollmentModel.status == RegistrationStatus.CONFIRMADA.value,
            )
        )
        return int(res.scalar_one())

    async def lock_row(self, event_id: UUID) -> None:
        """Adquiere FOR NO KEY UPDATE sobre la fila del evento (ADR-05)."""
        await self._s.execute(
            text("SELECT 1 FROM events WHERE id = :id FOR NO KEY UPDATE"),
            {"id": str(event_id)},
        )
