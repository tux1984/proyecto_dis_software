"""Adaptadores de pasarela de pagos (IPaymentAdapter, ADR-03, RF-04, RN-06).

``MockPaymentAdapter`` simula los cuatro estados del webhook (confirmed,
rejected, expired, duplicate). La idempotencia se garantiza aguas arriba con
``webhook_events.idempotency_key`` (UNIQUE). ``RealPaymentAdapter`` documenta el
punto de integración real (PSE/tarjetas) — sustituible por configuración.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.config import Settings
from app.domain.ports.adapters import PaymentIntent, WebhookResult


class MockPaymentAdapter:
    provider_name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._key = settings.payment_mock_key

    async def create_payment(
        self, enrollment_id: UUID, amount: float, return_url: str
    ) -> PaymentIntent:
        ref = f"mockpay_{uuid4().hex[:12]}"
        # La URL de la "pasarela" apunta de vuelta a la SPA con el ref del mock.
        url = f"{return_url}?payment_ref={ref}&enrollment_id={enrollment_id}"
        return PaymentIntent(payment_url=url, provider_reference=ref)

    def parse_webhook(self, payload: dict, signature: str | None) -> WebhookResult:
        # Validación de firma simplificada para el mock (HMAC en el real).
        if signature is not None and signature != self._key:
            raise ValueError("firma de webhook inválida")
        return WebhookResult(
            enrollment_id=UUID(str(payload["enrollment_id"])),
            status=payload.get("status", "confirmed"),
            idempotency_key=str(payload["idempotency_key"]),
            provider="mock",
        )

    async def get_payment_status(self, provider_reference: str) -> str:
        # El mock reconcilia siempre a un estado consistente (SAD §6.2.3).
        return "confirmed"


class RealPaymentAdapter:
    """Integración real (placeholder). No se usa en el POC (PAYMENT_PROVIDER=mock)."""

    provider_name = "real"

    def __init__(self, settings: Settings) -> None:
        self._key = settings.payment_mock_key

    async def create_payment(
        self, enrollment_id: UUID, amount: float, return_url: str
    ) -> PaymentIntent:  # pragma: no cover - no ejercitado en POC
        raise NotImplementedError(
            "Integración real con pasarela colombiana planificada (Fase 4)"
        )

    def parse_webhook(  # pragma: no cover
        self, payload: dict, signature: str | None
    ) -> WebhookResult:
        raise NotImplementedError

    async def get_payment_status(self, provider_reference: str) -> str:  # pragma: no cover
        raise NotImplementedError
