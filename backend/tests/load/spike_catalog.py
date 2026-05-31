"""Locust — prueba de PICO (spike) sobre el catálogo.

Carga base baja (10 VUs) → pico súbito a 200 VUs → recuperación. Demuestra que
la plataforma absorbe una ráfaga repentina y vuelve a la normalidad sin errores
(relacionado con disponibilidad/resiliencia, RNF-09).

    docker compose run --rm api locust -f tests/load/spike_catalog.py --headless \
      --host http://api:8000 --html tests/load/reports/spike_catalog.html \
      --csv tests/load/reports/spike_catalog
"""

from __future__ import annotations

from locust import HttpUser, LoadTestShape, between, task


class SpikeUser(HttpUser):
    wait_time = between(0.05, 0.2)

    @task(3)
    def catalog(self):
        self.client.get("/events", name="/events")

    @task(1)
    def semantic(self):
        self.client.get(
            "/search", params={"q": "datos", "semantic": "true"}, name="/search?semantic"
        )


class SpikeShape(LoadTestShape):
    """Base 10 VUs (20s) → pico 200 VUs (30s) → recuperación 10 VUs (30s)."""

    def tick(self):
        t = self.get_run_time()
        if t < 20:
            return (10, 10)
        if t < 50:
            return (200, 100)
        if t < 80:
            return (10, 20)
        return None
