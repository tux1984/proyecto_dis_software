"""RF-04 / RN-06 / R-02 — webhook de pago idempotente."""

from __future__ import annotations

import pytest

from tests.conftest import auth_header


@pytest.mark.integration
async def test_webhook_processed_once(client, make_user, make_event):
    attendee = await make_user(role="attendee")
    organizer = await make_user(role="organizer")
    event = await make_event(organizer.id, capacity=10, registration_type="paga")

    reg = await client.post(
        f"/enrollments/{event.id}/register", headers=auth_header(attendee), json={}
    )
    assert reg.status_code == 201
    body = reg.json()
    assert body["status"] == "pendiente_pago" and "payment_url" in body
    enrollment_id = body["enrollment_id"]

    payload = {
        "enrollment_id": enrollment_id,
        "status": "confirmed",
        "idempotency_key": f"idem-{enrollment_id}",
    }
    first = await client.post("/enrollments/webhook", json=payload)
    assert first.json() == {"status": "confirmada", "processed": True}

    second = await client.post("/enrollments/webhook", json=payload)
    assert second.json() == {"status": "duplicate", "processed": False}
