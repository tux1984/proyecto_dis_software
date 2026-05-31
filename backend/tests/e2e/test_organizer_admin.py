"""E2E — recorrido organizador/admin: sesiones, reportes, CSV, aprobación,
gestión de usuarios/roles, auditoría, categorías e iCal
(RF-06/09/11/14/16/24/26/27/29)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_header


@pytest.mark.e2e
async def test_organizer_event_management(client, make_user):
    organizer = await make_user(role="organizer")
    attendee = await make_user(role="attendee")
    now = datetime.now(tz=timezone.utc)

    create = await client.post(
        "/events", headers=auth_header(organizer),
        json={
            "title": "Congreso de gestión", "description": "x", "modality": "hibrido",
            "starts_at": (now + timedelta(days=10)).isoformat(),
            "ends_at": (now + timedelta(days=10, hours=8)).isoformat(), "capacity": 60,
        },
    )
    eid = create.json()["id"]

    # Editar (PATCH) por el dueño
    upd = await client.patch(
        f"/events/{eid}", headers=auth_header(organizer),
        json={"description": "Descripción actualizada", "capacity": 80},
    )
    assert upd.status_code == 200

    # Agenda: sesiones con detección de solape por track (RF-09)
    s1 = await client.post(
        f"/events/{eid}/sessions", headers=auth_header(organizer),
        json={"title": "Keynote", "track": "A",
              "starts_at": (now + timedelta(days=10, hours=1)).isoformat(),
              "ends_at": (now + timedelta(days=10, hours=2)).isoformat()},
    )
    assert s1.status_code == 201
    conflict = await client.post(
        f"/events/{eid}/sessions", headers=auth_header(organizer),
        json={"title": "Choca", "track": "A",
              "starts_at": (now + timedelta(days=10, hours=1, minutes=30)).isoformat(),
              "ends_at": (now + timedelta(days=10, hours=2, minutes=30)).isoformat()},
    )
    assert conflict.status_code == 400  # solape de horario en el mismo track

    await client.post(f"/events/{eid}/publish", headers=auth_header(organizer),
                      json={"request_approval": False})
    await client.post(f"/enrollments/{eid}/register", headers=auth_header(attendee), json={})

    # Detalle público incluye sesiones; iCal descargable (RF-16)
    detail = await client.get(f"/events/{eid}")
    assert len(detail.json()["sessions"]) == 1
    ics = await client.get(f"/events/{eid}/calendar.ics")
    assert ics.status_code == 200 and "BEGIN:VCALENDAR" in ics.text

    # Inscritos + exportación CSV (RF-11)
    inscritos = await client.get(f"/enrollments/event/{eid}", headers=auth_header(organizer))
    assert inscritos.json()["count"] >= 1
    csv = await client.get(f"/enrollments/event/{eid}/export.csv", headers=auth_header(organizer))
    assert csv.status_code == 200 and "email" in csv.text

    # Reportes del evento (RF-14)
    dash = await client.get(f"/events/{eid}/dashboard", headers=auth_header(organizer))
    assert dash.status_code == 200 and dash.json()["confirmed"] >= 1

    # Cancela el evento (RF-06)
    cancel = await client.post(f"/events/{eid}/cancel", headers=auth_header(organizer))
    assert cancel.json()["status"] == "cancelado"


@pytest.mark.e2e
async def test_admin_approval_users_roles_audit(client, make_user):
    organizer = await make_user(role="organizer")
    admin = await make_user(role="admin")
    now = datetime.now(tz=timezone.utc)

    # Evento que requiere aprobación -> pendiente
    create = await client.post(
        "/events", headers=auth_header(organizer),
        json={
            "title": "Evento institucional", "description": "x", "modality": "virtual",
            "starts_at": (now + timedelta(days=15)).isoformat(),
            "ends_at": (now + timedelta(days=15, hours=2)).isoformat(), "capacity": 20,
        },
    )
    eid = create.json()["id"]
    pub = await client.post(f"/events/{eid}/publish", headers=auth_header(organizer),
                            json={"request_approval": True})
    assert pub.json()["status"] == "pendiente"

    pending = await client.get("/admin/events/pending", headers=auth_header(admin))
    assert any(e["id"] == eid for e in pending.json()["events"])

    approve = await client.post(
        f"/events/{eid}/approve", headers=auth_header(admin),
        json={"comment": "Aprobado para publicación institucional."},
    )
    assert approve.json()["status"] == "publicado"

    # Gestión de usuarios y RBAC (RF-26)
    users = await client.get("/admin/users", headers=auth_header(admin))
    assert users.json()["users"]
    role_change = await client.post(
        f"/admin/users/{organizer.id}/role", headers=auth_header(admin),
        json={"role": "reviewer"},
    )
    assert role_change.json()["role"] == "reviewer"

    # Auditoría inmutable consultable (RF-29)
    audit = await client.get("/admin/audit", headers=auth_header(admin),
                             params={"action": "role_changed"})
    assert len(audit.json()["entries"]) >= 1


@pytest.mark.e2e
async def test_categories_public_and_admin(client, make_user):
    admin = await make_user(role="admin")
    created = await client.post(
        "/admin/categories", headers=auth_header(admin),
        json={"name": f"Categoría {datetime.now().timestamp()}", "faculty": "Ingeniería"},
    )
    assert created.status_code == 201
    listing = await client.get("/categories")
    assert listing.status_code == 200 and len(listing.json()["categories"]) >= 1


@pytest.mark.e2e
async def test_enrollment_cancellation(client, make_user):
    organizer = await make_user(role="organizer")
    attendee = await make_user(role="attendee")
    now = datetime.now(tz=timezone.utc)
    create = await client.post(
        "/events", headers=auth_header(organizer),
        json={
            "title": "Evento cancelable", "description": "x", "modality": "virtual",
            "starts_at": (now + timedelta(days=20)).isoformat(),
            "ends_at": (now + timedelta(days=20, hours=1)).isoformat(), "capacity": 10,
        },
    )
    eid = create.json()["id"]
    await client.post(f"/events/{eid}/publish", headers=auth_header(organizer),
                      json={"request_approval": False})
    reg = await client.post(f"/enrollments/{eid}/register", headers=auth_header(attendee), json={})
    enrollment_id = reg.json()["enrollment_id"]

    cancel = await client.post(
        f"/enrollments/{enrollment_id}/cancel", headers=auth_header(attendee)
    )
    assert cancel.json()["status"] == "cancelada"
