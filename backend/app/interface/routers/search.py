"""SearchRouter — descubrimiento de eventos (RF-01/02/30).

``GET /search?semantic=true`` activa la búsqueda semántica (pgvector) vía la
estrategia inyectada; sin el flag usa búsqueda textual. Endpoint público.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.application.search_service import SearchService
from app.domain.ports.repositories import CatalogFilters
from app.domain.value_objects import Modality
from app.interface.deps import get_search_service

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(
    q: str | None = Query(default=None, description="Texto de búsqueda"),
    semantic: bool = Query(default=False, description="Activa búsqueda semántica"),
    category_id: UUID | None = None,
    modality: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
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
    return {"count": len(results), "semantic": semantic, "results": results}
