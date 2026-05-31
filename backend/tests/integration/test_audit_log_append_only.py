"""ADR-10 / RF-29 / RN-07 — auditoría inmutable (append-only).

DELETE/UPDATE sobre ``audit_log`` están bloqueados por un trigger de BD
(SQLSTATE 42501). Cada operación prohibida se prueba en una sesión propia para
aislar el fallo del estado de la sesión async.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.infrastructure.db import SessionLocal
from app.infrastructure.repositories.audit_repository import AuditLogRepository


@pytest.mark.integration
async def test_append_works_but_delete_and_update_blocked(db, make_user):
    actor = await make_user(role="admin")
    # INSERT (append) funciona
    await AuditLogRepository(db).append(
        actor_user_id=actor.id, action="immutable_probe",
        entity_type="test", entity_id=uuid4(), result="success",
    )
    await db.commit()

    # DELETE bloqueado por el trigger (sesión propia para aislar el fallo)
    with pytest.raises(Exception) as exc_del:  # noqa: B017
        async with SessionLocal() as s:
            await s.execute(text("DELETE FROM audit_log WHERE action='immutable_probe'"))
            await s.commit()
    assert "append-only" in str(exc_del.value).lower() or "42501" in str(exc_del.value)

    # UPDATE bloqueado por el trigger
    with pytest.raises(Exception) as exc_upd:  # noqa: B017
        async with SessionLocal() as s:
            await s.execute(
                text("UPDATE audit_log SET action='x' WHERE action='immutable_probe'")
            )
            await s.commit()
    assert "append-only" in str(exc_upd.value).lower() or "42501" in str(exc_upd.value)

    # El registro original sigue presente (no se borró ni modificó)
    remaining = await db.execute(
        text("SELECT count(*) FROM audit_log WHERE action='immutable_probe'")
    )
    assert remaining.scalar_one() >= 1
