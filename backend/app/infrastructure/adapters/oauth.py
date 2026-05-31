"""Adaptadores de autenticación SSO (IOAuthAdapter, ADR-06, RF-28).

* ``MockOAuthAdapter``: el ``id_token`` es el correo institucional; "verifica"
  y devuelve la identidad. Permite demostrar el flujo SSO sin Google real.
* ``GoogleOAuthAdapter``: valida el ``id_token`` real contra Google (mismo
  contrato; sustitución por configuración, sin tocar AuthService).
"""

from __future__ import annotations

import httpx

from app.config import Settings
from app.domain.ports.adapters import OAuthIdentity


class MockOAuthAdapter:
    provider_name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._client_id = settings.oauth_client_id

    async def verify_id_token(self, id_token: str) -> OAuthIdentity:
        # En el mock, el id_token es el correo; derivamos un nombre legible.
        email = id_token.strip().lower()
        if "@" not in email:
            raise ValueError("id_token inválido (se esperaba correo en modo mock)")
        local = email.split("@", 1)[0]
        full_name = local.replace(".", " ").replace("_", " ").title()
        return OAuthIdentity(
            email=email, full_name=full_name, provider="mock", subject=email
        )

    def authorization_url(self, state: str) -> str:
        return f"/login?provider=mock&state={state}"


class GoogleOAuthAdapter:
    provider_name = "google"

    def __init__(self, settings: Settings) -> None:
        self._client_id = settings.oauth_client_id

    async def verify_id_token(self, id_token: str) -> OAuthIdentity:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("aud") != self._client_id:
            raise ValueError("audiencia del token no coincide con el client_id")
        return OAuthIdentity(
            email=data["email"],
            full_name=data.get("name", data["email"]),
            provider="google",
            subject=data["sub"],
        )

    def authorization_url(self, state: str) -> str:
        return (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={self._client_id}&response_type=code"
            f"&scope=openid%20email%20profile&state={state}"
        )
