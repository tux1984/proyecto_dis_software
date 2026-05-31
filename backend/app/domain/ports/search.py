"""Puerto de estrategia de búsqueda (patrón Strategy, ADR-07, RF-30).

``SearchService`` recibe una ``ISearchStrategy`` inyectada y no contiene
condicionales: ``TextSearchStrategy`` usa ``tsvector`` (GIN) y
``SemanticSearchStrategy`` usa el operador ``<=>`` de pgvector. Intercambiables
sin tocar el servicio.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.entities import Event
from app.domain.ports.repositories import CatalogFilters


class ISearchStrategy(Protocol):
    name: str

    async def search(
        self, filters: CatalogFilters, limit: int, offset: int
    ) -> list[Event]:
        ...
