"""Inyección de dependencias y seguridad (Dependency Injection + RBAC).

Construye los servicios de aplicación por request a partir de la sesión y los
adaptadores (Factory). ``get_current_user`` valida el JWT; ``require_role``
aplica RBAC en servidor (RNF-12) y audita los accesos denegados (E5 del SAD).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.admin_service import AdminService
from app.application.auth_service import AuthService
from app.application.certificate_service import CertificateService
from app.application.engagement_service import (
    AttendanceService,
    EvaluationService,
    MaterialService,
    SpeakerService,
)
from app.application.enrollment_handlers import (
    AuditHandler,
    CapacityMetricHandler,
    NotificationEnqueueHandler,
)
from app.application.enrollment_service import EnrollmentService
from app.application.event_service import EventService
from app.application.notification_service import NotificationService
from app.application.privacy_service import PrivacyService
from app.application.search_service import SearchService
from app.config import Settings, get_settings
from app.domain.errors import DomainError
from app.domain.ports.adapters import ICalendarAdapter
from app.domain.ports.handlers import IEnrollmentEventHandler
from app.domain.ports.search import ISearchStrategy
from app.infrastructure.adapters.factory import AdapterFactory
from app.infrastructure.db import SessionLocal, get_session
from app.infrastructure.queue.postgres_queue import PostgresJobQueue
from app.infrastructure.repositories.audit_repository import AuditLogRepository
from app.infrastructure.repositories.certificate_repository import CertificateRepository
from app.infrastructure.repositories.embedding_repository import EmbeddingRepository
from app.infrastructure.repositories.enrollment_repository import EnrollmentRepository
from app.infrastructure.repositories.event_repository import EventRepository
from app.infrastructure.repositories.notification_repository import NotificationRepository
from app.infrastructure.repositories.stats_repository import StatsRepository
from app.infrastructure.repositories.support_repository import (
    AttendanceRepository,
    CategoryRepository,
    EvaluationRepository,
    SessionRepository,
    SpeakerRepository,
    WebhookRepository,
)
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.search_strategies import (
    SemanticSearchStrategy,
    TextSearchStrategy,
)

_bearer = HTTPBearer(auto_error=False)
_factory = AdapterFactory()


@dataclass
class CurrentUser:
    id: UUID
    role: str
    email: str


class AuthError(DomainError):
    code = "unauthorized"


class ForbiddenError(DomainError):
    code = "forbidden"


def get_app_settings() -> Settings:
    return get_settings()


# ---- Autenticación ----------------------------------------------------------
async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    from app.infrastructure.security import TokenError, decode_token

    if creds is None:
        raise AuthError("Falta el token de autenticación")
    try:
        payload = decode_token(creds.credentials)
    except TokenError as exc:
        raise AuthError("Token inválido o expirado") from exc
    if payload.get("type") != "access":
        raise AuthError("Tipo de token inválido")

    user = CurrentUser(
        id=UUID(payload["sub"]), role=payload["role"], email=payload.get("email", "")
    )
    request.state.user_id = str(user.id)  # para el log de acceso (RNF-01)
    return user


def require_role(*roles: str):
    """RBAC server-side (RNF-12). El rol admin pasa todas las verificaciones."""

    async def checker(
        request: Request, user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if user.role != "admin" and user.role not in roles:
            await _audit_denied(request, user)
            raise ForbiddenError(
                f"Rol '{user.role}' insuficiente; se requiere uno de {roles}"
            )
        return user

    return checker


async def _audit_denied(request: Request, user: CurrentUser) -> None:
    """Registra el intento denegado en una transacción propia (E5)."""
    async with SessionLocal() as session:
        try:
            await AuditLogRepository(session).append(
                actor_user_id=user.id,
                action="access_denied",
                entity_type="route",
                entity_id=None,
                result="failure",
                ip_address=request.client.host if request.client else None,
            )
            await session.commit()
        except Exception:
            await session.rollback()


# ---- Factories de servicios -------------------------------------------------
def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(
        UserRepository(session), _factory.create_oauth(), AuditLogRepository(session)
    )


def get_notification_service(
    session: AsyncSession = Depends(get_session),
) -> NotificationService:
    return NotificationService(
        NotificationRepository(session),
        PostgresJobQueue(session),
        AuditLogRepository(session),
    )


def get_event_service(session: AsyncSession = Depends(get_session)) -> EventService:
    return EventService(
        events=EventRepository(session),
        audit=AuditLogRepository(session),
        embedding=_factory.create_embedding(),
        sessions=SessionRepository(session),
        notifier=NotificationService(
            NotificationRepository(session),
            PostgresJobQueue(session),
            AuditLogRepository(session),
        ),
    )


def get_enrollment_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> EnrollmentService:
    events = EventRepository(session)
    audit = AuditLogRepository(session)
    queue = PostgresJobQueue(session)
    handlers: list[IEnrollmentEventHandler] = [
        NotificationEnqueueHandler(queue),   # Observer: encola correo
        CapacityMetricHandler(events),       # Observer: métrica de cupo
        AuditHandler(audit),                 # Observer: auditoría
    ]
    return EnrollmentService(
        enrollments=EnrollmentRepository(session),
        events=events,
        audit=audit,
        payment=_factory.create_payment(),
        queue=queue,
        webhooks=WebhookRepository(session),
        handlers=handlers,
        settings=settings,
    )


def get_search_service(
    semantic: bool = False, session: AsyncSession = Depends(get_session)
) -> SearchService:
    """Selecciona la estrategia (Strategy) según el flag ``semantic``."""
    event_repo = EventRepository(session)
    text_strategy = TextSearchStrategy(event_repo)
    strategy: ISearchStrategy = text_strategy
    if semantic:
        # Usa pgvector real solo si hay embeddings de OpenAI configurados; de lo
        # contrario, mapa semántico curado + respaldo textual (demo determinista).
        use_vector = get_settings().embedding_provider == "openai"
        strategy = SemanticSearchStrategy(
            _factory.create_embedding(), EmbeddingRepository(session),
            text_strategy, event_repo, use_vector,
        )
    return SearchService(strategy)


def get_certificate_service(
    session: AsyncSession = Depends(get_session),
) -> CertificateService:
    return CertificateService(
        CertificateRepository(session),
        AttendanceRepository(session),
        EnrollmentRepository(session),
        PostgresJobQueue(session),
        AuditLogRepository(session),
    )


def get_admin_service(session: AsyncSession = Depends(get_session)) -> AdminService:
    return AdminService(
        UserRepository(session), AuditLogRepository(session), StatsRepository(session)
    )


def get_privacy_service(session: AsyncSession = Depends(get_session)) -> PrivacyService:
    return PrivacyService(
        UserRepository(session),
        EnrollmentRepository(session),
        AuditLogRepository(session),
    )


def get_speaker_service(session: AsyncSession = Depends(get_session)) -> SpeakerService:
    return SpeakerService(
        SpeakerRepository(session), PostgresJobQueue(session), AuditLogRepository(session)
    )


def get_attendance_service(
    session: AsyncSession = Depends(get_session),
) -> AttendanceService:
    return AttendanceService(
        AttendanceRepository(session),
        EnrollmentRepository(session),
        AuditLogRepository(session),
    )


def get_evaluation_service(
    session: AsyncSession = Depends(get_session),
) -> EvaluationService:
    return EvaluationService(EvaluationRepository(session), AttendanceRepository(session))


def get_material_service(
    session: AsyncSession = Depends(get_session),
) -> MaterialService:
    return MaterialService(
        EnrollmentRepository(session), EventRepository(session), SpeakerRepository(session)
    )


def get_category_repository(
    session: AsyncSession = Depends(get_session),
) -> CategoryRepository:
    return CategoryRepository(session)


def get_calendar_adapter() -> ICalendarAdapter:
    return _factory.create_calendar()
