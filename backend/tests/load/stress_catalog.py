"""Locust — STRESS escalonado del catálogo (4x el requisito RNF-06).

Sube la carga por escalones 50 → 100 → 150 → 200 VUs (30 s c/u) para mostrar
cómo evoluciona el p95 más allá de los 50 VUs exigidos por el SRS. Demuestra el
margen de capacidad de lectura del catálogo y la búsqueda.

    docker compose run --rm api locust -f tests/load/stress_catalog.py --headless \
      --host http://api:8000 --html tests/load/reports/stress_catalog.html \
      --csv tests/load/reports/stress_catalog
"""

from __future__ import annotations

import random

from locust import HttpUser, LoadTestShape, between, task


class CatalogStressUser(HttpUser):
    wait_time = between(0.05, 0.3)

    @task(4)
    def catalog(self):
        params = random.choice(
            [{}, {"modality": "virtual"}, {"sort": "date_desc"}, {"q": "inteligencia"}]
        )
        self.client.get("/events", params=params, name="/events")

    @task(2)
    def semantic(self):
        self.client.get(
            "/search", params={"q": "machine learning", "semantic": "true"},
            name="/search?semantic",
        )


class StepLoadShape(LoadTestShape):
    """Escalones acumulativos (fin de cada etapa en segundos)."""

    stages = [
        {"end": 30, "users": 50, "rate": 25},
        {"end": 60, "users": 100, "rate": 25},
        {"end": 90, "users": 150, "rate": 25},
        {"end": 120, "users": 200, "rate": 25},
    ]

    def tick(self):
        t = self.get_run_time()
        for s in self.stages:
            if t < s["end"]:
                return (s["users"], s["rate"])
        return None
