"""E2E CU-03 / RF-12 — envío masivo asíncrono (no bloquea, 202)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_header


@pytest.mark.e2e
async def test_broadcast_enqueues_and_returns_202(client, make_user):
    organizer = await make_user(role="organizer")
    attendee = await make_user(role="attendee")
    now = datetime.now(tz=timezone.utc)

    create = await client.post(
        "/events", headers=auth_header(organizer),
        json={
            "title": "Evento con comunicaciones", "description": "x", "modality": "virtual",
            "starts_at": (now + timedelta(days=4)).isoformat(),
            "ends_at": (now + timedelta(days=4, hours=1)).isoformat(), "capacity": 50,
        },
    )
    event_id = create.json()["id"]
    await client.post(f"/events/{event_id}/publish", headers=auth_header(organizer),
                      json={"request_approval": False})
    await client.post(f"/enrollments/{event_id}/register", headers=auth_header(attendee), json={})

    resp = await client.post(
        f"/notifications/{event_id}/broadcast",
        headers=auth_header(organizer),
        json={"subject": "Recordatorio", "body": "Nos vemos pronto", "segment": "confirmed"},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "queued" and data["recipients"] >= 1

    status = await client.get(
        f"/notifications/{data['notification_id']}/status", headers=auth_header(organizer)
    )
    assert status.status_code == 200
