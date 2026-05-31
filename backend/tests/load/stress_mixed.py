"""Locust — STRESS de carga MIXTA realista (alta concurrencia).

Simula tráfico real combinado a 100 VUs (5x el escenario de inscripción del
SRS): cada usuario inicia sesión y reparte su actividad entre navegar el
catálogo, buscar (semántica), ver detalle de evento e inscribirse. Demuestra
que el sistema responde bajo una mezcla exigente, no solo lecturas.

    docker compose run --rm api locust -f tests/load/stress_mixed.py --headless \
      -u 100 -r 25 -t 2m --host http://api:8000 \
      --html tests/load/reports/stress_mixed.html --csv tests/load/reports/stress_mixed
"""

from __future__ import annotations

import random
import uuid

from locust import HttpUser, between, task


class MixedUser(HttpUser):
    wait_time = between(0.1, 0.6)

    def on_start(self):
        email = f"stress_{uuid.uuid4().hex}@javeriana.edu.co"
        resp = self.client.post("/auth/login", json={"id_token": email})
        self.token = resp.json().get("access_token") if resp.status_code == 200 else None
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        catalog = self.client.get("/events", params={"limit": 50})
        results = catalog.json().get("results", []) if catalog.status_code == 200 else []
        self.events = [e["id"] for e in results]
        self.free = [e["id"] for e in results if e["registration_type"] == "gratuita"]

    @task(5)
    def browse(self):
        self.client.get("/events", params={"sort": "date_desc"}, name="/events")

    @task(3)
    def semantic(self):
        self.client.get(
            "/search", params={"q": "ciberseguridad", "semantic": "true"},
            name="/search?semantic",
        )

    @task(3)
    def detail(self):
        if self.events:
            self.client.get(f"/events/{random.choice(self.events)}", name="/events/{id}")

    @task(1)
    def enroll(self):
        if self.token and self.free:
            eid = random.choice(self.free)
            with self.client.post(
                f"/enrollments/{eid}/register", headers=self.headers, json={},
                name="/enrollments/register", catch_response=True,
            ) as r:
                if r.status_code in (201, 409):   # 409 duplicado/sin cupo es válido
                    r.success()
