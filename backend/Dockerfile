# =============================================================================
# Imagen única del backend PGEA — usada por API, Worker y suite de pruebas
# (ADR-01: un solo Dockerfile produce la imagen del monolito).
# =============================================================================
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Permite construir tras un proxy corporativo con interceptación TLS (MITM).
    # Se aplica también a los subprocesos de build-isolation (PEP 517).
    PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"

WORKDIR /app

# Curl para healthchecks ad-hoc; el resto de deps son wheels puros.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Código de la aplicación + manifiesto del paquete
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY scripts ./scripts
COPY tests ./tests

# Instalación editable: el paquete vive en /app/app (compatible con el
# montaje de volumen en desarrollo y con --reload).
RUN pip install --upgrade pip && pip install -e ".[dev]"

# Almacenamiento local de PDFs de certificados (volumen en compose)
RUN mkdir -p /app/storage/certificates

EXPOSE 8000

# Por defecto arranca el API; el worker y los tests sobreescriben 'command'.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
