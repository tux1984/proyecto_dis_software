"""JWT propio HS256 (ADR-06, RNF-11).

Tras validar el ``id_token`` externo (SSO), el sistema emite un JWT propio con
``sub``, ``role`` y ``exp``. Las rutas protegidas lo validan; al ser stateless,
habilita escalado horizontal trivial (N réplicas tras balanceador).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt

from app.config import get_settings


class TokenError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(tz=UTC)


def create_access_token(user_id: UUID, role: str, email: str) -> str:
    s = get_settings()
    payload = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "type": "access",
        "exp": _now() + timedelta(minutes=s.access_token_expire_minutes),
        "iat": _now(),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_refresh_token(user_id: UUID) -> str:
    s = get_settings()
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": _now() + timedelta(days=s.refresh_token_expire_days),
        "iat": _now(),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
