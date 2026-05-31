"""Puerto de observador de eventos de dominio (patrón Observer, SAD §9.2).

``EnrollmentService`` publica ``EnrollmentConfirmed``; cada handler reacciona de
forma desacoplada (encolar correo, actualizar métrica de cupo, auditar). El
emisor no conoce a sus observadores.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.events import DomainEvent


class IEnrollmentEventHandler(Protocol):
    async def handle(self, event: DomainEvent) -> None:
        ...
