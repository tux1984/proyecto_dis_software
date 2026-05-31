"""RNF-12 / E5 — RBAC en servidor y auditoría del acceso denegado."""

from __future__ import annotations

import pytest

from tests.conftest import auth_header


@pytest.mark.integration
async def test_attendee_denied_admin_dashboard(client, make_user):
    attendee = await make_user(role="attendee")
    resp = await client.get("/admin/dashboard", headers=auth_header(attendee))
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden"


@pytest.mark.integration
async def test_admin_allowed_admin_dashboard(client, make_user):
    admin = await make_user(role="admin")
    resp = await client.get("/admin/dashboard", headers=auth_header(admin))
    assert resp.status_code == 200
    assert "total_events" in resp.json()


@pytest.mark.integration
async def test_denied_access_is_audited(client, db, make_user):
    attendee = await make_user(role="attendee")
    await client.get("/admin/users", headers=auth_header(attendee))

    from sqlalchemy import select

    from app.infrastructure.models import AuditLogModel

    rows = (
        await db.execute(
            select(AuditLogModel).where(
                AuditLogModel.actor_user_id == attendee.id,
                AuditLogModel.action == "access_denied",
            )
        )
    ).scalars().all()
    assert len(rows) >= 1 and rows[0].result == "failure"
