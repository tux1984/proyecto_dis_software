"""Modelos ORM SQLAlchemy — modelo físico PostgreSQL 16 + pgvector (SAD §7).

Cinco áreas: identidad/acceso, gestión de eventos, inscripciones/pagos,
comunicaciones/certificación y auditoría/búsqueda. Las CHECK constraints
materializan los catálogos cerrados; ``audit_log`` es append-only a nivel de BD
(REVOKE en la migración, ADR-10).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.infrastructure.db import Base

_DIM = get_settings().embedding_dimensions


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _ts(default_now: bool = False) -> Mapped[datetime]:
    if default_now:
        return mapped_column(DateTime(timezone=True), server_default=func.now())
    return mapped_column(DateTime(timezone=True), nullable=True)


# ---- 1) Identidad y acceso --------------------------------------------------
class RoleModel(Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    description: Mapped[str] = mapped_column(Text, default="")


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('organizer','attendee','speaker','reviewer','admin')",
            name="role_valid",
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="attendee")
    auth_provider: Mapped[str] = mapped_column(String(40), default="mock")
    consent_accepted_at: Mapped[datetime] = _ts()
    is_anonymized: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = _ts(default_now=True)


class CategoryModel(Base):
    __tablename__ = "categories"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    faculty: Mapped[str] = mapped_column(String(120), default="")
    parent_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )


# ---- 2) Gestión de eventos --------------------------------------------------
class EventModel(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint("ends_at > starts_at", name="dates_coherent"),
        CheckConstraint(
            "modality IN ('presencial','virtual','hibrido')", name="modality_valid"
        ),
        CheckConstraint(
            "status IN ('borrador','pendiente','publicado','cancelado')",
            name="status_valid",
        ),
        Index("ix_events_status_starts_at", "status", "starts_at"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    modality: Mapped[str] = mapped_column(String(20), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str] = mapped_column(String(512), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="borrador")
    registration_type: Mapped[str] = mapped_column(String(20), default="gratuita")
    organizer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(_DIM), nullable=True)
    created_at: Mapped[datetime] = _ts(default_now=True)
    published_at: Mapped[datetime] = _ts()


class EventSessionModel(Base):
    __tablename__ = "event_sessions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    track: Mapped[str] = mapped_column(String(120), nullable=True)
    speaker_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class EventSpeakerModel(Base):
    __tablename__ = "event_speakers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('invitado','confirmado','declinado')", name="speaker_status_valid"
        ),
        UniqueConstraint("invite_token", name="uq_event_speakers_invite_token"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="invitado")
    bio: Mapped[str] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str] = mapped_column(String(512), nullable=True)
    material_url: Mapped[str] = mapped_column(String(512), nullable=True)
    invite_token: Mapped[str] = mapped_column(String(64), nullable=True)


# ---- 3) Inscripciones y pagos -----------------------------------------------
class EnrollmentModel(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pendiente_pago','confirmada','cancelada','expirada')",
            name="enrollment_status_valid",
        ),
        UniqueConstraint("event_id", "user_id", name="uq_enrollments_event_id_user_id"),
        Index("ix_enrollments_event_id_status", "event_id", "status"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(120), nullable=True)
    form_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    registered_at: Mapped[datetime] = _ts(default_now=True)
    confirmed_at: Mapped[datetime] = _ts()
    cancelled_at: Mapped[datetime] = _ts()
    reserved_until: Mapped[datetime] = _ts()


class PaymentModel(Base):
    __tablename__ = "payments"
    id: Mapped[uuid.UUID] = _uuid_pk()
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("enrollments.id"), unique=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    paid_at: Mapped[datetime] = _ts()


# ---- 4) Comunicaciones, asistencia y certificación --------------------------
class CertificateModel(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        CheckConstraint(
            "type IN ('asistencia','ponencia','organizacion')", name="cert_type_valid"
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), default="asistencia")
    verification_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    pdf_url: Mapped[str] = mapped_column(String(512), nullable=True)
    generated_at: Mapped[datetime] = _ts(default_now=True)


class AttendanceRecordModel(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_attendance_event_user"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("event_sessions.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(40), default="manual")
    recorded_at: Mapped[datetime] = _ts(default_now=True)


class NotificationModel(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("segment IN ('all','confirmed','cancelled')", name="segment_valid"),
        CheckConstraint(
            "status IN ('queued','running','completed','failed')", name="notif_status_valid"
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    segment: Mapped[str] = mapped_column(String(20), default="confirmed")
    status: Mapped[str] = mapped_column(String(20), default="queued")
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    started_at: Mapped[datetime] = _ts()
    completed_at: Mapped[datetime] = _ts()


class NotificationDeliveryModel(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint("status IN ('pending','sent','failed')", name="delivery_status_valid"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    notification_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = _ts()


class EvaluationModel(Base):
    __tablename__ = "evaluations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _ts(default_now=True)


# ---- 5) Asíncrono / webhooks ------------------------------------------------
class WebhookEventModel(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_webhook_events_idempotency_key"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime] = _ts(default_now=True)
    related_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=True
    )


class QueuedJobModel(Base):
    __tablename__ = "queued_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('send_email','generate_certificate')", name="job_type_valid"
        ),
        CheckConstraint(
            "status IN ('pending','processing','done','failed')", name="job_status_valid"
        ),
        Index("ix_queued_jobs_status_next_retry", "status", "next_retry_at"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime] = _ts()
    created_at: Mapped[datetime] = _ts(default_now=True)
    processed_at: Mapped[datetime] = _ts()


class FailedJobModel(Base):
    __tablename__ = "failed_jobs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    failed_at: Mapped[datetime] = _ts(default_now=True)


# ---- 6) Auditoría inmutable (append-only, ADR-10) ---------------------------
class AuditLogModel(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint("result IN ('success','failure')", name="audit_result_valid"),
        Index("ix_audit_log_occurred_at_actor", "occurred_at", "actor_user_id"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    trace_id: Mapped[str] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str] = mapped_column(INET, nullable=True)
    occurred_at: Mapped[datetime] = _ts(default_now=True)
