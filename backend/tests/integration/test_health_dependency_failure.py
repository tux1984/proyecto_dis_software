"""RNF-04 / RNF-09 — health checks de liveness y readiness."""

from __future__ import annotations

import pytest


@pytest.mark.integration
async def test_liveness_ok(client):
    resp = await client.get("/health/live")
    assert resp.status_code == 200 and resp.json()["status"] == "alive"


@pytest.mark.integration
async def test_readiness_reports_dependencies(client):
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["queue"] == "ok"
    # Nota: la verificación del modo "degraded" (dependencia caída) se valida en
    # la demo deteniendo el contenedor de PostgreSQL (RNF-09, runbook).
