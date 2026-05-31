"""Adaptadores de embeddings (IEmbeddingAdapter, ADR-07, RF-30).

* ``OpenAIEmbeddingAdapter``: ``text-embedding-3-small`` con ``dimensions=384``
  (coincide con la columna ``vector(384)`` e índice IVFFlat del SAD).
* ``FakeEmbeddingAdapter``: vector determinista a partir del hash del texto,
  normalizado. Usado en tests/CI para no depender de la API (mismo contrato).
"""

from __future__ import annotations

import hashlib
import math
import time

from app.config import Settings
from app.observability.metrics import EMBEDDING_DURATION


class OpenAIEmbeddingAdapter:
    provider_name = "openai"

    def __init__(self, settings: Settings) -> None:
        from openai import AsyncOpenAI

        self.dimensions = settings.embedding_dimensions
        self._model = settings.embedding_model
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def embed(self, text: str) -> list[float]:
        start = time.perf_counter()
        try:
            resp = await self._client.embeddings.create(
                model=self._model, input=text, dimensions=self.dimensions
            )
            return resp.data[0].embedding
        finally:
            EMBEDDING_DURATION.labels(provider="openai").observe(
                time.perf_counter() - start
            )


class FakeEmbeddingAdapter:
    """Embeddings deterministas para pruebas (sin red).

    Genera un vector pseudoaleatorio reproducible por texto y lo normaliza, de
    modo que textos iguales dan vectores iguales y textos similares (que
    comparten tokens) tienden a acercarse. Suficiente para validar el flujo
    completo de búsqueda semántica en CI.
    """

    provider_name = "fake"

    def __init__(self, settings: Settings) -> None:
        self.dimensions = settings.embedding_dimensions

    async def embed(self, text: str) -> list[float]:
        start = time.perf_counter()
        try:
            return self._deterministic_vector(text)
        finally:
            EMBEDDING_DURATION.labels(provider="fake").observe(
                time.perf_counter() - start
            )

    def _deterministic_vector(self, text: str) -> list[float]:
        # Suma de vectores por token (bolsa de palabras hash) → captura
        # similitud léxica de forma estable y reproducible.
        vec = [0.0] * self.dimensions
        tokens = text.lower().split() or [text.lower()]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(self.dimensions):
                # byte determinista por dimensión, centrado en 0
                b = digest[i % len(digest)]
                vec[i] += (b - 128) / 128.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
