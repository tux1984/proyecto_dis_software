"""Puertos hacia sistemas externos (patrón Adapter, ADR-03).

Cada integración externa se expresa como un ``Protocol``; el servicio depende
de la abstracción, no del proveedor. Las implementaciones mock y real cumplen
el mismo contrato (verificado con pruebas de contrato, RNF-14/15).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID


# ---- Autenticación SSO (OAuth 2.0 / OIDC) -----------------------------------
@dataclass(frozen=True, slots=True)
class OAuthIdentity:
    """Identidad federada devuelta por el proveedor SSO."""

    email: str
    full_name: str
    provider: str
    subject: str


@runtime_checkable
class IOAuthAdapter(Protocol):
    async def verify_id_token(self, id_token: str) -> OAuthIdentity:
        """Valida el ``id_token`` externo y devuelve la identidad (RF-28)."""
        ...

    def authorization_url(self, state: str) -> str:
        """URL de redirección al proveedor (inicio del flujo OAuth)."""
        ...


# ---- Pasarela de pagos ------------------------------------------------------
@dataclass(frozen=True, slots=True)
class PaymentIntent:
    payment_url: str
    provider_reference: str


@dataclass(frozen=True, slots=True)
class WebhookResult:
    enrollment_id: UUID
    status: str            # "confirmed" | "rejected" | "expired"
    idempotency_key: str
    provider: str


@runtime_checkable
class IPaymentAdapter(Protocol):
    async def create_payment(
        self, enrollment_id: UUID, amount: float, return_url: str
    ) -> PaymentIntent:
        """Inicia el pago y devuelve la URL de la pasarela (RF-04)."""
        ...

    def parse_webhook(self, payload: dict, signature: str | None) -> WebhookResult:
        """Valida y normaliza el webhook (idempotente aguas arriba, RN-06)."""
        ...

    async def get_payment_status(self, provider_reference: str) -> str:
        """Estado del pago para reconciliación nocturna."""
        ...


# ---- Correo -----------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    body: str


@runtime_checkable
class IEmailAdapter(Protocol):
    provider_name: str

    async def send(self, message: EmailMessage) -> None:
        """Envía (o simula) un correo. Lanza excepción ante fallo (reintentos)."""
        ...


# ---- Embeddings (búsqueda semántica) ----------------------------------------
@runtime_checkable
class IEmbeddingAdapter(Protocol):
    provider_name: str
    dimensions: int

    async def embed(self, text: str) -> list[float]:
        """Genera el vector de embedding del texto (RF-30, ADR-07)."""
        ...


# ---- Calendario (.ics) ------------------------------------------------------
@runtime_checkable
class ICalendarAdapter(Protocol):
    def build_ics(
        self,
        *,
        uid: str,
        title: str,
        description: str,
        starts_at,
        ends_at,
        location: str | None,
    ) -> str:
        """Genera un archivo iCal RFC 5545 (RF-16)."""
        ...
