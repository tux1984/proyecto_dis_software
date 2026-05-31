"""Locust — RNF-06: catálogo bajo carga típica (p95 <= 500ms, 50 VUs).

Ejecución:
    locust -f tests/load/catalog_p95.py --headless -u 50 -r 10 -t 1m \
        --host http://api:8000 --csv=catalog
"""

from __future__ import annotations

import random

from locust import HttpUser, between, task


class CatalogUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(4)
    def list_catalog(self):
        params = random.choice(
            [{}, {"modality": "virtual"}, {"sort": "date_desc"}, {"q": "inteligencia"}]
        )
        self.client.get("/events", params=params, name="/events")

    @task(1)
    def semantic_search(self):
        self.client.get(
            "/search",
            params={"q": "inteligencia artificial", "semantic": "true"},
            name="/search?semantic",
        )
