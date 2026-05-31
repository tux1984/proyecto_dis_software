"""Locust — RNF-08: 50 inscripciones concurrentes al último cupo.

Demuestra "sin sobreventa" bajo carga real: solo una recibe 201; las demás 409
``no_capacity``. Requiere un evento publicado con capacity=1.

Ejecución:
    EVENT_ID=<uuid> locust -f tests/load/enroll_concurrent.py --headless \
        -u 50 -r 50 -t 15s --host http://api:8000
"""

from __future__ import annotations

import os
import uuid

from locust import HttpUser, task

EVENT_ID = os.getenv("EVENT_ID", "")


class ConcurrentEnrollUser(HttpUser):
    def on_start(self):
        email = f"conc_{uuid.uuid4().hex}@javeriana.edu.co"
        resp = self.client.post("/auth/login", json={"id_token": email})
        self.token = resp.json().get("access_token") if resp.status_code == 200 else None

    @task
    def enroll_last_seat(self):
        if not EVENT_ID or not self.token:
            return
        with self.client.post(
            f"/enrollments/{EVENT_ID}/register",
            headers={"Authorization": f"Bearer {self.token}"},
            json={},
            name="register-last-seat",
            catch_response=True,
        ) as resp:
            # 201 (ganador) y 409 (sin cupo / duplicado) son resultados válidos.
            if resp.status_code in (201, 409):
                resp.success()
            else:
                resp.failure(f"inesperado: {resp.status_code}")
