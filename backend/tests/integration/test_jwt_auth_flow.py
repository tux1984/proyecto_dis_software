"""RF-28 / ADR-06 — autenticación SSO mock + JWT propio."""

from __future__ import annotations

import pytest


@pytest.mark.integration
async def test_login_returns_jwt_and_me_works(client):
    resp = await client.post("/auth/login", json={"id_token": "ana.perez@javeriana.edu.co"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer" and data["user"]["email"] == "ana.perez@javeriana.edu.co"

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "ana.perez@javeriana.edu.co"


@pytest.mark.integration
async def test_missing_token_is_401(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_invalid_token_is_401(client):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_refresh_issues_new_access_token(client):
    login = await client.post("/auth/login", json={"id_token": "ref.user@javeriana.edu.co"})
    refresh = login.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200 and "access_token" in resp.json()
