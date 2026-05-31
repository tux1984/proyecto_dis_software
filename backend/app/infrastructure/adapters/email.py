"""Adaptadores de correo (IEmailAdapter, ADR-03, RN-08).

* ``MockEmailAdapter``: no envía; registra cada "envío" como log estructurado
  con ``trace_id`` (evidencia operacional sin proveedor externo, SAD §6.4.1).
* ``SmtpEmailAdapter``: envío real por SMTP (producción).
* ``InMemoryEmailAdapter``: captura mensajes en memoria (pruebas de contrato).

Las tres cumplen el mismo contrato → intercambiables (RNF-14/15, E6 del SAD).
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage as MimeMessage

from app.config import Settings
from app.domain.ports.adapters import EmailMessage

logger = logging.getLogger("pgea.email")


class MockEmailAdapter:
    provider_name = "mock"

    async def send(self, message: EmailMessage) -> None:
        # El "envío" queda trazado en Loki con el trace_id del request/job.
        logger.info(
            "email_sent (mock)",
            extra={"to": message.to, "subject": message.subject, "provider": "mock"},
        )


class InMemoryEmailAdapter:
    """Adaptador de pruebas: acumula mensajes; misma interfaz que el real."""

    provider_name = "memory"

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


class SmtpEmailAdapter:
    provider_name = "smtp"

    def __init__(self, settings: Settings) -> None:
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._user = settings.smtp_username
        self._password = settings.smtp_password
        self._from = settings.email_from

    async def send(self, message: EmailMessage) -> None:
        # smtplib es síncrono: ejecutarlo en un hilo evita bloquear el event loop.
        await asyncio.get_running_loop().run_in_executor(None, self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._from
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            smtp.starttls()
            if self._user:
                smtp.login(self._user, self._password)
            smtp.send_message(mime)
