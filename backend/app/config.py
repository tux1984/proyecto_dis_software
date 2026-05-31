"""Configuración tipada y validada al arranque (SAD §10.5).

Usa ``pydantic-settings`` para cargar variables de entorno con validación
fuerte. Falla rápido si una variable crítica falta o es inválida.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración global de la aplicación.

    Las variables se documentan en ``.env.example``. Selección de adaptadores
    (email, oauth, payment, embedding) por configuración, no por código
    (RNF-15, RNF-16, ADR-03).
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- Entorno ----
    env: Literal["dev", "stage", "prod", "test"] = "dev"

    # ---- Base de datos ----
    database_url: str = "postgresql+asyncpg://pgea_app_user:change_me_in_local_env@postgres:5432/pgea"

    # ---- Autenticación / JWT (ADR-06) ----
    jwt_secret: str = "change_me_use_openssl_rand_hex_32"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    refresh_token_expire_days: int = 7
    oauth_provider: Literal["mock", "google"] = "mock"
    oauth_client_id: str = "pgea-mock-client"
    oauth_client_secret: str = "pgea-mock-secret"

    # ---- Pasarela de pagos (RF-04, RN-06) ----
    payment_provider: Literal["mock", "real"] = "mock"
    payment_mock_key: str = "pgea-mock-payment-key"
    payment_reservation_timeout_minutes: int = 15

    # ---- Correo (ADR-03, RN-08) ----
    email_provider: Literal["mock", "smtp"] = "mock"
    email_from: str = "eventos@javeriana.edu.co"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_rate_limit_per_second: int = 10

    # ---- Embeddings / búsqueda semántica (RF-30, ADR-07) ----
    embedding_provider: Literal["openai", "fake"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 384
    openai_api_key: str = ""

    # ---- Observabilidad (ADR-04) ----
    service_name: str = "pgea-api"
    otel_enabled: bool = True
    otel_exporter_otlp_endpoint: str = "http://tempo:4317"
    loki_endpoint: str = "http://loki:3100/loki/api/v1/push"
    log_level: str = "INFO"

    # ---- Worker ----
    worker_poll_interval_seconds: float = 2.0
    worker_max_retries: int = 5

    @property
    def is_test(self) -> bool:
        return self.env == "test"


@lru_cache
def get_settings() -> Settings:
    """Singleton de settings (cargado una vez por proceso)."""
    return Settings()
