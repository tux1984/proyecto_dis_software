"""Caché in-memory con TTL (patrón Cache-Aside, SAD §9.1, RNF-06).

El catálogo se lee primero de BD y se sirve de caché en lecturas subsiguientes
durante un TTL corto (consistencia eventual aceptable: publicar/cancelar es
poco frecuente frente a la navegación). En el POC la caché es por proceso;
escalar a >1 réplica requeriría Redis (deuda técnica documentada).
"""

from __future__ import annotations

import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float = 10.0, max_size: int = 256) -> None:
        self._ttl = ttl_seconds
        self._max = max_size
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self._max:
            self._store.clear()  # política simple para el POC
        self._store[key] = (time.monotonic() + self._ttl, value)

    def invalidate(self, prefix: str = "") -> None:
        if not prefix:
            self._store.clear()
            return
        for k in [k for k in self._store if k.startswith(prefix)]:
            self._store.pop(k, None)


# Caché compartida del catálogo (por proceso).
catalog_cache = TTLCache(ttl_seconds=10.0)
