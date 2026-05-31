"""Repositorio de auditoría append-only (RF-29, RN-07, ADR-10).

Solo expone ``append`` y ``query``: no hay método de update/delete a nivel de
aplicación, y el trigger de BD bloquea cualquier mutación (defensa en
profundidad). Cada entrada lleva el ``trace_id`` para correlación operacional.
"""

from __future__ import annotations

from uuid import UUID

from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import AuditLogModel


def _current_trace_id() -> str | None:
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx and ctx.is_valid:
        return format(ctx.trace_id, "032x")
    return None


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def append(
        self,
        *,
        actor_user_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID | None,
        result: str = "success",
        trace_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        self._s.add(
            AuditLogModel(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                result=result,
                trace_id=trace_id or _current_trace_id(),
                ip_address=ip_address,
            )
        )
        await self._s.flush()

    async def query(
        self,
        *,
        action: str | None = None,
        actor_user_id: UUID | None = None,
        limit: int = 100,
    ) -> list[dict]:
        stmt = select(AuditLogModel).order_by(AuditLogModel.occurred_at.desc())
        if action:
            stmt = stmt.where(AuditLogModel.action == action)
        if actor_user_id:
            stmt = stmt.where(AuditLogModel.actor_user_id == actor_user_id)
        res = await self._s.execute(stmt.limit(limit))
        return [
            {
                "id": str(m.id),
                "actor_user_id": str(m.actor_user_id) if m.actor_user_id else None,
                "action": m.action,
                "entity_type": m.entity_type,
                "entity_id": str(m.entity_id) if m.entity_id else None,
                "result": m.result,
                "trace_id": m.trace_id,
                "occurred_at": m.occurred_at.isoformat() if m.occurred_at else None,
            }
            for m in res.scalars().all()
        ]
