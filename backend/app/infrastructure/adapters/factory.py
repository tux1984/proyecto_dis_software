"""``AdapterFactory`` — Factory Method de adaptadores (SAD §9.2).

Recibe la configuración y devuelve la implementación del puerto según la
variable de entorno (``EMAIL_PROVIDER``, ``OAUTH_PROVIDER``, …). Añadir un
proveedor nuevo es agregar una clase y un caso, sin tocar la lógica de negocio.
Cambiar de proveedor en la demo = cambiar la env y reiniciar (E6 del SAD).
"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.domain.ports.adapters import (
    ICalendarAdapter,
    IEmailAdapter,
    IEmbeddingAdapter,
    IOAuthAdapter,
    IPaymentAdapter,
)
from app.infrastructure.adapters.calendar import IcsCalendarAdapter
from app.infrastructure.adapters.email import (
    InMemoryEmailAdapter,
    MockEmailAdapter,
    SmtpEmailAdapter,
)
from app.infrastructure.adapters.embedding import (
    FakeEmbeddingAdapter,
    OpenAIEmbeddingAdapter,
)
from app.infrastructure.adapters.oauth import GoogleOAuthAdapter, MockOAuthAdapter
from app.infrastructure.adapters.payment import MockPaymentAdapter, RealPaymentAdapter

# El adaptador de embeddings se cachea (mantiene el cliente OpenAI reutilizable).
_embedding_singleton: IEmbeddingAdapter | None = None


class AdapterFactory:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()

    def create_oauth(self) -> IOAuthAdapter:
        if self._s.oauth_provider == "google":
            return GoogleOAuthAdapter(self._s)
        return MockOAuthAdapter(self._s)

    def create_payment(self) -> IPaymentAdapter:
        if self._s.payment_provider == "real":
            return RealPaymentAdapter(self._s)
        return MockPaymentAdapter(self._s)

    def create_email(self) -> IEmailAdapter:
        if self._s.is_test:
            return InMemoryEmailAdapter()
        if self._s.email_provider == "smtp":
            return SmtpEmailAdapter(self._s)
        return MockEmailAdapter()

    def create_embedding(self) -> IEmbeddingAdapter:
        global _embedding_singleton
        if _embedding_singleton is None:
            if self._s.embedding_provider == "openai":
                _embedding_singleton = OpenAIEmbeddingAdapter(self._s)
            else:
                _embedding_singleton = FakeEmbeddingAdapter(self._s)
        return _embedding_singleton

    def create_calendar(self) -> ICalendarAdapter:
        return IcsCalendarAdapter()
