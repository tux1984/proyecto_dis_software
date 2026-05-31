"""Estrategias de búsqueda concretas (patrón Strategy, ADR-07, RF-30).

Implementan ``ISearchStrategy``. ``SearchService`` recibe una u otra inyectada y
no contiene ``if semantic`` en su lógica.

``SemanticSearchStrategy`` resuelve la consulta en este orden:
  1. **Mapa semántico curado** (demo determinista): para temas conocidos
     (IA, ciberseguridad, salud…) devuelve los eventos relacionados aunque no
     compartan las palabras exactas.
  2. **pgvector** (solo si ``use_vector``, es decir con embeddings reales de
     OpenAI configurados): búsqueda por similitud coseno.
  3. **Búsqueda textual** como respaldo, sin romper la experiencia (SAD §6.2.8).
"""

from __future__ import annotations

import logging

from opentelemetry import trace

from app.domain.entities import Event
from app.domain.ports.adapters import IEmbeddingAdapter
from app.domain.ports.repositories import CatalogFilters
from app.infrastructure.curated_search import match_curated_titles
from app.infrastructure.repositories.embedding_repository import EmbeddingRepository
from app.infrastructure.repositories.event_repository import EventRepository

logger = logging.getLogger("pgea.search")
_tracer = trace.get_tracer("pgea.search")


class TextSearchStrategy:
    """Búsqueda textual (tsvector GIN) + filtros estructurados (RF-01/02)."""

    name = "text"

    def __init__(self, event_repo: EventRepository) -> None:
        self._events = event_repo

    async def search(
        self, filters: CatalogFilters, limit: int, offset: int
    ) -> list[Event]:
        return await self._events.search_catalog(filters, limit, offset)


class SemanticSearchStrategy:
    """Búsqueda semántica por similitud coseno con pgvector (RF-30)."""

    name = "semantic"

    def __init__(
        self,
        embedding_adapter: IEmbeddingAdapter,
        embedding_repo: EmbeddingRepository,
        fallback: TextSearchStrategy,
        events: EventRepository,
        use_vector: bool = False,
    ) -> None:
        self._embed = embedding_adapter
        self._repo = embedding_repo
        self._fallback = fallback
        self._events = events
        self._use_vector = use_vector

    async def search(
        self, filters: CatalogFilters, limit: int, offset: int
    ) -> list[Event]:
        if not filters.query:
            # Sin texto no hay semántica: cae a listado estructurado.
            return await self._fallback.search(filters, limit, offset)

        with _tracer.start_as_current_span("search.semantic_query") as span:
            span.set_attribute("query.text", filters.query)

            # 1) Mapa semántico curado (demo determinista).
            fragments = match_curated_titles(filters.query)
            if fragments:
                span.set_attribute("semantic.mode", "curated")
                results = await self._events.search_by_titles(fragments, filters, limit)
                if results:
                    span.set_attribute("results.count", len(results))
                    return results

            # 2) pgvector real (solo con embeddings de OpenAI configurados).
            if self._use_vector:
                try:
                    span.set_attribute("semantic.mode", "vector")
                    vector = await self._embed.embed(filters.query)
                    results = await self._repo.semantic_search(vector, filters, limit)
                    if results:
                        span.set_attribute("results.count", len(results))
                        return results
                except Exception as exc:  # degradación controlada
                    logger.warning("Búsqueda vectorial falló, degradando a texto: %s", exc)

        # 3) Respaldo: búsqueda textual relevante.
        return await self._fallback.search(filters, limit, offset)
