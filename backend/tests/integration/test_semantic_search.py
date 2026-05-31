"""RF-30 / ADR-07 — búsqueda híbrida: textual + semántica (pgvector)."""

from __future__ import annotations

import pytest

from tests.conftest import auth_header


async def _create_published_event(client, organizer, title, description):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(tz=timezone.utc)
    create = await client.post(
        "/events",
        headers=auth_header(organizer),
        json={
            "title": title,
            "description": description,
            "modality": "virtual",
            "starts_at": (now + timedelta(days=3)).isoformat(),
            "ends_at": (now + timedelta(days=3, hours=2)).isoformat(),
            "capacity": 50,
        },
    )
    assert create.status_code == 201
    eid = create.json()["id"]
    # Publicar genera el embedding (adaptador fake en tests).
    pub = await client.post(
        f"/events/{eid}/publish", headers=auth_header(organizer),
        json={"request_approval": False},
    )
    assert pub.status_code == 200
    return eid


@pytest.mark.integration
async def test_textual_search_finds_event(client, make_user):
    organizer = await make_user(role="organizer")
    await _create_published_event(
        client, organizer,
        "Taller de aprendizaje profundo",
        "Redes neuronales convolucionales y modelos de deep learning.",
    )
    resp = await client.get("/search", params={"q": "aprendizaje profundo"})
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()["results"]]
    assert any("aprendizaje profundo" in t.lower() for t in titles)


@pytest.mark.integration
async def test_semantic_search_returns_results(client, make_user):
    organizer = await make_user(role="organizer")
    await _create_published_event(
        client, organizer,
        "Congreso de inteligencia artificial",
        "Machine learning, redes neuronales y embeddings semánticos.",
    )
    resp = await client.get(
        "/search", params={"q": "inteligencia artificial", "semantic": "true"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["semantic"] is True
    assert data["count"] >= 1  # el flujo semántico devuelve resultados
