"""Locust — RNF-07: inscripción gratuita bajo carga (p95 <= 2s, 20 VUs).

Ejecución:
    locust -f tests/load/enroll_p95.py --headless -u 20 -r 5 -t 1m \
        --host http://api:8000 --csv=enroll
"""

from __future__ import annotations

import random
import uuid

from locust import HttpUser, between, task


class EnrollUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self):
        email = f"load_{uuid.uuid4().hex}@javeriana.edu.co"
        resp = self.client.post("/auth/login", json={"id_token": email})
        self.token = resp.json().get("access_token") if resp.status_code == 200 else None
        catalog = self.client.get("/events", params={"limit": 50})
        self.events = (
            [e["id"] for e in catalog.json()["results"] if e["registration_type"] == "gratuita"]
            if catalog.status_code == 200
            else []
        )

    @task
    def enroll(self):
        if not self.token or not self.events:
            return
        event_id = random.choice(self.events)
        self.client.post(
            f"/enrollments/{event_id}/register",
            headers={"Authorization": f"Bearer {self.token}"},
            json={},
            name="/enrollments/register",
        )
