"""SearchService — catálogo y descubrimiento (RF-01/02/30).

No contiene condicionales de tipo de búsqueda: recibe una ``ISearchStrategy``
inyectada (texto o semántica). El catálogo por defecto usa Cache-Aside para
cumplir el SLO de latencia (RNF-06).
"""

from __future__ import annotations

from app.domain.entities import Event
from app.domain.ports.repositories import CatalogFilters
from app.domain.ports.search import ISearchStrategy
from app.infrastructure.cache import catalog_cache


class SearchService:
    def __init__(self, strategy: ISearchStrategy) -> None:
        self._strategy = strategy

    async def search(
        self, filters: CatalogFilters, limit: int = 20, offset: int = 0
    ) -> list[dict]:
        # Cache-Aside solo para la ruta caliente del catálogo (texto, sin query).
        cacheable = self._strategy.name == "text" and not filters.query
        cache_key = self._cache_key(filters, limit, offset) if cacheable else None
        if cache_key:
            cached = catalog_cache.get(cache_key)
            if cached is not None:
                return cached

        events = await self._strategy.search(filters, limit, offset)
        result = [self._to_dict(e) for e in events]
        if cache_key:
            catalog_cache.set(cache_key, result)
        return result

    @staticmethod
    def _cache_key(filters: CatalogFilters, limit: int, offset: int) -> str:
        return (
            f"catalog:{filters.category_id}:{filters.modality}:"
            f"{filters.date_from}:{filters.date_to}:{filters.sort}:{limit}:{offset}"
        )

    @staticmethod
    def _to_dict(e: Event) -> dict:
        return {
            "id": str(e.id),
            "title": e.title,
            "description": e.description,
            "modality": e.modality.value,
            "starts_at": e.starts_at.isoformat(),
            "ends_at": e.ends_at.isoformat(),
            "location": e.location,
            "capacity": e.capacity,
            "registration_type": e.registration_type.value,
            "category_id": str(e.category_id) if e.category_id else None,
            "status": e.status.value,
        }
