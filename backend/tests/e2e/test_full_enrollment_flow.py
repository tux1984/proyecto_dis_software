"""E2E CU-01 + CU-02 — crear, publicar e inscribirse a un evento."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_header


@pytest.mark.e2e
async def test_create_publish_enroll_confirm(client, make_user):
    organizer = await make_user(role="organizer")
    attendee = await make_user(role="attendee")
    now = datetime.now(tz=timezone.utc)

    # CU-02: crear evento (borrador)
    create = await client.post(
        "/events",
        headers=auth_header(organizer),
        json={
            "title": "Seminario E2E de Arquitectura",
            "description": "Patrones, capas y observabilidad.",
            "modality": "hibrido",
            "starts_at": (now + timedelta(days=7)).isoformat(),
            "ends_at": (now + timedelta(days=7, hours=3)).isoformat(),
            "capacity": 30,
        },
    )
    assert create.status_code == 201
    event_id = create.json()["id"]
    assert create.json()["status"] == "borrador"

    # Publicar -> aparece en catálogo
    pub = await client.post(
        f"/events/{event_id}/publish", headers=auth_header(organizer),
        json={"request_approval": False},
    )
    assert pub.status_code == 200 and pub.json()["status"] == "publicado"

    # CU-01: inscribirse (gratuita -> confirmada)
    reg = await client.post(
        f"/enrollments/{event_id}/register", headers=auth_header(attendee), json={}
    )
    assert reg.status_code == 201 and reg.json()["status"] == "confirmada"

    # Aparece en "mis inscripciones"
    mine = await client.get("/enrollments/mine", headers=auth_header(attendee))
    assert any(e["event_id"] == event_id for e in mine.json()["enrollments"])

    # Inscripción duplicada -> 409
    dup = await client.post(
        f"/enrollments/{event_id}/register", headers=auth_header(attendee), json={}
    )
    assert dup.status_code == 409 and dup.json()["error"] == "duplicate_registration"


@pytest.mark.e2e
async def test_non_owner_cannot_edit_event(client, make_user):
    owner = await make_user(role="organizer")
    other = await make_user(role="organizer")
    now = datetime.now(tz=timezone.utc)
    create = await client.post(
        "/events", headers=auth_header(owner),
        json={
            "title": "Evento propietario", "description": "x", "modality": "virtual",
            "starts_at": (now + timedelta(days=2)).isoformat(),
            "ends_at": (now + timedelta(days=2, hours=1)).isoformat(), "capacity": 10,
        },
    )
    event_id = create.json()["id"]
    resp = await client.patch(
        f"/events/{event_id}", headers=auth_header(other), json={"title": "hackeado"}
    )
    assert resp.status_code == 403
