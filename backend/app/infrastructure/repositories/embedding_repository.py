"""Repositorio de búsqueda vectorial con pgvector (RF-30, ADR-07).

Ejecuta k-NN por similitud coseno (operador ``<=>``) sobre la columna
``events.embedding``, respetando los filtros estructurados y la visibilidad del
catálogo (solo PUBLICADO, RN-03).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Event
from app.domain.ports.repositories import CatalogFilters
from app.domain.value_objects import EventStatus
from app.infrastructure.models import EventModel
from app.infrastructure.repositories.mappers import to_event


class EmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def semantic_search(
        self, query_vector: list[float], filters: CatalogFilters, limit: int
    ) -> list[Event]:
        stmt = (
            select(EventModel)
            .where(EventModel.status == EventStatus.PUBLICADO.value)
            .where(EventModel.embedding.isnot(None))
        )
        if filters.category_id:
            stmt = stmt.where(EventModel.category_id == filters.category_id)
        if filters.modality:
            stmt = stmt.where(EventModel.modality == filters.modality.value)
        if filters.date_from:
            stmt = stmt.where(EventModel.starts_at >= filters.date_from)
        if filters.date_to:
            stmt = stmt.where(EventModel.starts_at <= filters.date_to)

        # k vecinos más cercanos por distancia coseno (pgvector <=>)
        stmt = stmt.order_by(
            EventModel.embedding.cosine_distance(query_vector)
        ).limit(limit)

        res = await self._s.execute(stmt)
        return [to_event(m) for m in res.scalars().all()]
