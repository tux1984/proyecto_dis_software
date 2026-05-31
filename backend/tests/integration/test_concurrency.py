"""RNF-08 / RN-01 — consistencia de cupos bajo concurrencia (ADR-05).

50 inscripciones simultáneas al último cupo: exactamente una se confirma y las
demás reciben 409 ``no_capacity``; cero sobreventa. Valida el bloqueo pesimista
``SELECT … FOR NO KEY UPDATE`` de ``EnrollmentRepository``.
"""

from __future__ import annotations

import asyncio

import pytest

from tests.conftest import token_for


@pytest.mark.integration
async def test_50_concurrent_registrations_no_oversell(client, db, make_user, make_event):
    organizer = await make_user(role="organizer")
    event = await make_event(organizer.id, capacity=1, status="publicado")

    users = [await make_user(role="attendee") for _ in range(50)]
    tokens = [token_for(u) for u in users]

    async def register(tok: str):
        resp = await client.post(
            f"/enrollments/{event.id}/register",
            headers={"Authorization": f"Bearer {tok}"},
            json={},
        )
        return resp.status_code

    results = await asyncio.gather(*(register(t) for t in tokens))

    confirmed = sum(1 for r in results if r == 201)
    no_capacity = sum(1 for r in results if r == 409)

    assert confirmed == 1, f"esperado 1 confirmada, hubo {confirmed}"
    assert no_capacity == 49, f"esperado 49 rechazos, hubo {no_capacity}"

    # Verificación de consistencia en BD: nunca más confirmadas que la capacidad.
    from sqlalchemy import func, select

    from app.infrastructure.models import EnrollmentModel

    count = await db.scalar(
        select(func.count()).select_from(EnrollmentModel).where(
            EnrollmentModel.event_id == event.id,
            EnrollmentModel.status == "confirmada",
        )
    )
    assert count == 1  # cero sobreventa
