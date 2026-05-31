# =============================================================================
# PGEA — Makefile de conveniencia para el POC
# =============================================================================
.DEFAULT_GOAL := help
COMPOSE := docker compose
COMPOSE_TEST := docker compose -f docker-compose.yml -f docker-compose.test.yml

.PHONY: help
help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: env
env: ## Crea .env desde la plantilla si no existe
	@test -f .env || (cp .env.example .env && echo "✓ .env creado desde .env.example — completa OPENAI_API_KEY y JWT_SECRET")

.PHONY: build
build: ## Construye todas las imágenes
	$(COMPOSE) build

.PHONY: up
up: env ## Levanta todo el stack (api, worker, db, nginx, observabilidad)
	$(COMPOSE) up -d --build
	@echo "Esperando readiness del API..."
	@until curl -sf http://localhost:8080/api/health/ready >/dev/null 2>&1; do sleep 2; done
	@echo "✓ Stack arriba.  SPA: http://localhost:8080  Grafana: http://localhost:3000"

.PHONY: down
down: ## Detiene el stack (conserva volúmenes)
	$(COMPOSE) down

.PHONY: clean
clean: ## Detiene el stack y borra volúmenes (BD, grafana, loki)
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Sigue los logs de api y worker
	$(COMPOSE) logs -f api worker

.PHONY: ps
ps: ## Estado de los contenedores
	$(COMPOSE) ps

.PHONY: migrate
migrate: ## Aplica migraciones Alembic
	$(COMPOSE) exec api alembic upgrade head

.PHONY: makemigration
makemigration: ## Genera una migración (uso: make makemigration m="mensaje")
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"

.PHONY: seed
seed: ## Puebla la BD con datos sintéticos (genera embeddings)
	$(COMPOSE) exec api python -m scripts.seed_data

.PHONY: clean-loadtest
clean-loadtest: ## Depura inscripciones/datos de usuarios de pruebas de carga (libera cupos)
	$(COMPOSE) exec api python -m scripts.clean_loadtest

.PHONY: test
test: ## Ejecuta la suite pytest con cobertura (BD efímera)
	$(COMPOSE_TEST) run --rm api-test

.PHONY: lint
lint: ## ruff + mypy sobre el backend
	$(COMPOSE) run --rm --no-deps api ruff check app && \
	$(COMPOSE) run --rm --no-deps api mypy app

.PHONY: load
load: ## Pruebas de carga Locust (catálogo RNF-06 + inscripción RNF-07) con reporte HTML
	@mkdir -p backend/tests/load/reports
	$(COMPOSE) run --rm api locust -f tests/load/catalog_p95.py --headless -u 50 -r 10 -t 1m \
	  --host http://api:8000 --html tests/load/reports/catalog_p95.html --csv tests/load/reports/catalog_p95
	$(COMPOSE) run --rm api locust -f tests/load/enroll_p95.py --headless -u 20 -r 5 -t 1m \
	  --host http://api:8000 --html tests/load/reports/enroll_p95.html --csv tests/load/reports/enroll_p95
	@echo "✓ Reportes HTML + CSV en backend/tests/load/reports/"

.PHONY: load-concurrent
load-concurrent: ## Locust de concurrencia al último cupo (uso: make load-concurrent EVENT_ID=<uuid>)
	@test -n "$(EVENT_ID)" || (echo "Falta EVENT_ID. Crea un evento con capacity=1 y publícalo." && exit 1)
	@mkdir -p backend/tests/load/reports
	$(COMPOSE) run --rm -e EVENT_ID=$(EVENT_ID) api locust -f tests/load/enroll_concurrent.py \
	  --headless -u 50 -r 50 -t 15s --host http://api:8000 \
	  --html tests/load/reports/enroll_concurrent.html --csv tests/load/reports/enroll_concurrent

.PHONY: load-stress
load-stress: ## Pruebas EXIGENTES: escalonada (200 VUs), mixta (100 VUs) y de pico, con reporte HTML
	@mkdir -p backend/tests/load/reports
	$(COMPOSE) run --rm api locust -f tests/load/stress_catalog.py --headless \
	  --host http://api:8000 --html tests/load/reports/stress_catalog.html --csv tests/load/reports/stress_catalog
	$(COMPOSE) run --rm api locust -f tests/load/stress_mixed.py --headless -u 100 -r 25 -t 2m \
	  --host http://api:8000 --html tests/load/reports/stress_mixed.html --csv tests/load/reports/stress_mixed
	$(COMPOSE) run --rm api locust -f tests/load/spike_catalog.py --headless \
	  --host http://api:8000 --html tests/load/reports/spike_catalog.html --csv tests/load/reports/spike_catalog
	@echo "✓ Reportes exigentes en backend/tests/load/reports/"

.PHONY: shell
shell: ## Shell dentro del contenedor API
	$(COMPOSE) exec api bash

.PHONY: psql
psql: ## Cliente psql contra la BD
	$(COMPOSE) exec postgres psql -U pgea_app_user -d pgea
