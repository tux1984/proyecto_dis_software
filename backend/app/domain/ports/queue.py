"""Puerto de la cola interna (patrón Producer-Consumer, ADR-09).

Los servicios *producen* jobs; el ``worker`` los *consume* con
``SELECT … FOR UPDATE SKIP LOCKED``. Encolar es una escritura en la misma
transacción que la operación de negocio (outbox), garantizando que no se pierde
trabajo si el proceso cae tras el commit.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class IJobQueue(Protocol):
    async def enqueue(self, job_type: str, payload: dict) -> UUID:
        """Encola un job (``send_email`` | ``generate_certificate``)."""
        ...
