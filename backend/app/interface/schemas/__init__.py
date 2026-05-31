"""DTOs Pydantic v2 (patrón Builder, SAD §9.2).

Los ``model_validator`` validan invariantes de entrada campo a campo antes de
construir el comando que consume el servicio de aplicación; el dominio vuelve a
validar sus propias reglas (defensa en profundidad).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ---- Auth -------------------------------------------------------------------
class LoginRequest(BaseModel):
    # En modo mock el id_token es el correo institucional.
    id_token: str = Field(min_length=3)


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


# ---- Eventos ----------------------------------------------------------------
class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = ""
    modality: str
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(gt=0)
    registration_type: str = "gratuita"
    location: str | None = None
    external_url: str | None = None
    category_id: UUID | None = None

    @field_validator("modality")
    @classmethod
    def _modality_valid(cls, v: str) -> str:
        if v not in {"presencial", "virtual", "hibrido"}:
            raise ValueError("modality inválida")
        return v

    @model_validator(mode="after")
    def _dates_coherent(self) -> EventCreate:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at debe ser posterior a starts_at")
        return self


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    modality: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    capacity: int | None = Field(default=None, gt=0)
    registration_type: str | None = None
    location: str | None = None
    external_url: str | None = None
    category_id: UUID | None = None


class PublishRequest(BaseModel):
    request_approval: bool = False


class ApprovalRequest(BaseModel):
    comment: str = Field(min_length=20)


class SessionCreate(BaseModel):
    title: str = Field(min_length=2)
    starts_at: datetime
    ends_at: datetime
    track: str | None = None
    speaker_id: UUID | None = None

    @model_validator(mode="after")
    def _dates(self) -> SessionCreate:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at debe ser posterior a starts_at")
        return self


# ---- Inscripciones ----------------------------------------------------------
class EnrollRequest(BaseModel):
    form_data: dict[str, Any] | None = None


class PaymentWebhook(BaseModel):
    enrollment_id: UUID
    status: str = "confirmed"           # confirmed | rejected | expired
    idempotency_key: str


# ---- Notificaciones ---------------------------------------------------------
class BroadcastRequest(BaseModel):
    subject: str = Field(min_length=2)
    body: str = Field(min_length=2)
    segment: str = "confirmed"

    @field_validator("segment")
    @classmethod
    def _segment_valid(cls, v: str) -> str:
        if v not in {"all", "confirmed", "cancelled"}:
            raise ValueError("segment inválido")
        return v


# ---- Certificados / ponentes / asistencia / evaluación ----------------------
class CertificateRequest(BaseModel):
    cert_type: str = "asistencia"


class SpeakerInvite(BaseModel):
    email: EmailStr


class SpeakerRespond(BaseModel):
    accept: bool
    bio: str | None = None
    material_url: str | None = None


class AttendanceRecord(BaseModel):
    user_id: UUID
    session_id: UUID | None = None


class EvaluationSubmit(BaseModel):
    payload: dict[str, Any]


# ---- Admin ------------------------------------------------------------------
class RoleChange(BaseModel):
    role: str


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2)
    faculty: str = ""
