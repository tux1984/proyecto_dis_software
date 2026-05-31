"""Pruebas de contrato de adaptadores (RNF-14/15, ADR-03, E6 del SAD).

Distintas implementaciones del mismo ``Protocol`` cumplen el contrato; esto
sustenta la sustitución por configuración sin tocar la lógica de negocio.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.config import get_settings
from app.domain.ports.adapters import (
    EmailMessage,
    IEmailAdapter,
    IEmbeddingAdapter,
)
from app.infrastructure.adapters.email import InMemoryEmailAdapter, MockEmailAdapter
from app.infrastructure.adapters.embedding import FakeEmbeddingAdapter
from app.infrastructure.adapters.factory import AdapterFactory
from app.infrastructure.adapters.oauth import MockOAuthAdapter
from app.infrastructure.adapters.payment import MockPaymentAdapter


@pytest.mark.contract
@pytest.mark.parametrize("adapter", [MockEmailAdapter(), InMemoryEmailAdapter()])
async def test_email_adapters_share_contract(adapter: IEmailAdapter):
    # Ambos cumplen la interfaz: no lanzan al enviar y exponen provider_name.
    assert isinstance(adapter, IEmailAdapter)
    await adapter.send(EmailMessage(to="a@b.co", subject="s", body="b"))
    assert adapter.provider_name in {"mock", "memory"}


@pytest.mark.contract
async def test_in_memory_email_captures():
    adapter = InMemoryEmailAdapter()
    await adapter.send(EmailMessage(to="x@y.co", subject="hola", body="cuerpo"))
    assert len(adapter.sent) == 1 and adapter.sent[0].subject == "hola"


@pytest.mark.contract
async def test_fake_embedding_is_deterministic_and_sized():
    adapter: IEmbeddingAdapter = FakeEmbeddingAdapter(get_settings())
    v1 = await adapter.embed("inteligencia artificial")
    v2 = await adapter.embed("inteligencia artificial")
    assert v1 == v2  # determinista
    assert len(v1) == get_settings().embedding_dimensions == 384


@pytest.mark.contract
async def test_oauth_mock_returns_identity():
    adapter = MockOAuthAdapter(get_settings())
    identity = await adapter.verify_id_token("jane.doe@javeriana.edu.co")
    assert identity.email == "jane.doe@javeriana.edu.co"
    assert identity.full_name == "Jane Doe"


@pytest.mark.contract
async def test_payment_webhook_parse():
    adapter = MockPaymentAdapter(get_settings())
    enr = uuid4()
    result = adapter.parse_webhook(
        {"enrollment_id": str(enr), "status": "confirmed", "idempotency_key": "k1"}, None
    )
    assert result.enrollment_id == enr and result.status == "confirmed"


@pytest.mark.contract
def test_factory_selects_by_config(monkeypatch):
    # EMAIL_PROVIDER controla la implementación devuelta (Factory Method).
    s = get_settings()
    object.__setattr__(s, "env", "dev")
    object.__setattr__(s, "email_provider", "mock")
    assert AdapterFactory(s).create_email().provider_name == "mock"
