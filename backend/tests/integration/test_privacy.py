"""RNF-10 / RN-07 — Ley 1581: consulta, supresión y log de acceso a PII."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.infrastructure.models import AuditLogModel
from tests.conftest import auth_header


@pytest.mark.integration
async def test_get_my_data_logs_pii_access(client, db, make_user):
    user = await make_user(role="attendee")
    resp = await client.get("/me/data", headers=auth_header(user))
    assert resp.status_code == 200 and resp.json()["email"] == user.email

    rows = (
        await db.execute(
            select(AuditLogModel).where(
                AuditLogModel.actor_user_id == user.id,
                AuditLogModel.action == "pii_access",
            )
        )
    ).scalars().all()
    assert len(rows) >= 1


@pytest.mark.integration
async def test_delete_my_data_anonymizes(client, make_user):
    user = await make_user(role="attendee")
    original_email = user.email
    deleted = await client.delete("/me/data", headers=auth_header(user))
    assert deleted.status_code == 200 and deleted.json()["status"] == "anonymized"

    after = await client.get("/me/data", headers=auth_header(user))
    assert after.json()["email"] != original_email
    assert after.json()["full_name"] == "ANONIMIZADO"


@pytest.mark.integration
async def test_admin_can_read_pii_access_log(client, make_user):
    user = await make_user(role="attendee")
    await client.get("/me/data", headers=auth_header(user))  # genera un acceso PII
    admin = await make_user(role="admin")
    resp = await client.get("/admin/pii-access", headers=auth_header(admin))
    assert resp.status_code == 200 and len(resp.json()["entries"]) >= 1
