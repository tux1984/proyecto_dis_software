"""Integración — asistencia, certificados, ponentes, material y evaluación
(RF-10/13/18/19/20/21/22, RN-05/09)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_header


async def _published_event(client, organizer):
    now = datetime.now(tz=timezone.utc)
    create = await client.post(
        "/events", headers=auth_header(organizer),
        json={
            "title": "Evento de participación", "description": "Sesiones y ponentes.",
            "modality": "presencial",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=1, hours=4)).isoformat(), "capacity": 40,
        },
    )
    eid = create.json()["id"]
    await client.post(f"/events/{eid}/publish", headers=auth_header(organizer),
                      json={"request_approval": False})
    return eid


@pytest.mark.integration
async def test_attendance_certificate_and_verification(client, make_user):
    organizer = await make_user(role="organizer")
    attendee = await make_user(role="attendee")
    eid = await _published_event(client, organizer)

    # Inscripción confirmada (gratuita)
    await client.post(f"/enrollments/{eid}/register", headers=auth_header(attendee), json={})

    # Sin asistencia: el certificado se rechaza (RN-05 -> 403)
    denied = await client.post(
        f"/certificates/{eid}/request", headers=auth_header(attendee),
        json={"cert_type": "asistencia"},
    )
    assert denied.status_code == 403

    # El organizador registra asistencia (RF-19)
    att = await client.post(
        f"/events/{eid}/attendance", headers=auth_header(organizer),
        json={"user_id": str(attendee.id)},
    )
    assert att.status_code == 201

    # Ahora sí emite certificado con código verificable (RF-21)
    cert = await client.post(
        f"/certificates/{eid}/request", headers=auth_header(attendee),
        json={"cert_type": "asistencia"},
    )
    assert cert.status_code == 200
    code = cert.json()["verification_code"]

    # Verificación pública del código
    verify = await client.get(f"/certificates/verify/{code}")
    assert verify.status_code == 200 and verify.json()["valid"] is True

    mine = await client.get("/certificates/mine", headers=auth_header(attendee))
    assert mine.status_code == 200

    # Generación batch por el organizador (RF-13)
    batch = await client.post(
        f"/certificates/{eid}/batch", headers=auth_header(organizer),
        json={"cert_type": "asistencia"},
    )
    assert batch.status_code == 202


@pytest.mark.integration
async def test_attendance_requires_confirmed_enrollment(client, make_user):
    organizer = await make_user(role="organizer")
    stranger = await make_user(role="attendee")
    eid = await _published_event(client, organizer)
    # Usuario sin inscripción confirmada -> 422 (RF-19)
    resp = await client.post(
        f"/events/{eid}/attendance", headers=auth_header(organizer),
        json={"user_id": str(stranger.id)},
    )
    assert resp.status_code == 422


@pytest.mark.integration
async def test_material_access_depends_on_enrollment(client, make_user):
    organizer = await make_user(role="organizer")
    confirmed = await make_user(role="attendee")
    outsider = await make_user(role="attendee")
    eid = await _published_event(client, organizer)
    await client.post(f"/enrollments/{eid}/register", headers=auth_header(confirmed), json={})

    full = await client.get(f"/events/{eid}/material", headers=auth_header(confirmed))
    assert full.json()["access"] == "full"

    public = await client.get(f"/events/{eid}/material", headers=auth_header(outsider))
    assert public.json()["access"] == "public"


@pytest.mark.integration
async def test_speaker_invite_and_respond(client, make_user):
    organizer = await make_user(role="organizer")
    eid = await _published_event(client, organizer)
    invite = await client.post(
        f"/events/{eid}/speakers", headers=auth_header(organizer),
        json={"email": "ponente.test@externo.com"},
    )
    assert invite.status_code == 201
    token = invite.json()["invite_token"]

    accept = await client.post(
        "/speakers/respond", params={"token": token},
        json={"accept": True, "bio": "Doctor en IA", "material_url": "http://x/m.pdf"},
    )
    assert accept.status_code == 200 and accept.json()["status"] == "confirmado"

    speakers = await client.get(f"/events/{eid}/speakers")
    assert any(s["email"] == "ponente.test@externo.com" for s in speakers.json()["speakers"])

    # Token de un solo uso: reusar falla
    reuse = await client.post(
        "/speakers/respond", params={"token": token}, json={"accept": True}
    )
    assert reuse.status_code == 400


@pytest.mark.integration
async def test_evaluation_requires_attendance(client, make_user):
    organizer = await make_user(role="organizer")
    attendee = await make_user(role="attendee")
    eid = await _published_event(client, organizer)
    await client.post(f"/enrollments/{eid}/register", headers=auth_header(attendee), json={})

    # Sin asistencia -> 403
    no_att = await client.post(
        f"/events/{eid}/evaluation", headers=auth_header(attendee),
        json={"payload": {"score": 5}},
    )
    assert no_att.status_code == 403

    await client.post(f"/events/{eid}/attendance", headers=auth_header(organizer),
                      json={"user_id": str(attendee.id)})
    ok = await client.post(
        f"/events/{eid}/evaluation", headers=auth_header(attendee),
        json={"payload": {"score": 5, "comment": "Excelente"}},
    )
    assert ok.status_code == 201
