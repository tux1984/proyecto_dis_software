"""Repositorio de certificados (RF-13, RF-21, RN-05)."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import CertificateModel, EventModel, UserModel


class CertificateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def exists(self, user_id: UUID, event_id: UUID, cert_type: str) -> bool:
        res = await self._s.execute(
            select(CertificateModel.id).where(
                CertificateModel.user_id == user_id,
                CertificateModel.event_id == event_id,
                CertificateModel.type == cert_type,
            )
        )
        return res.first() is not None

    async def create(
        self,
        *,
        user_id: UUID,
        event_id: UUID,
        cert_type: str,
        verification_code: str,
        enrollment_id: UUID | None = None,
        pdf_url: str | None = None,
    ) -> UUID:
        cert_id = uuid4()
        self._s.add(
            CertificateModel(
                id=cert_id,
                user_id=user_id,
                event_id=event_id,
                type=cert_type,
                verification_code=verification_code,
                enrollment_id=enrollment_id,
                pdf_url=pdf_url,
            )
        )
        await self._s.flush()
        return cert_id

    async def get_for(self, user_id: UUID, event_id: UUID, cert_type: str) -> dict | None:
        res = await self._s.execute(
            select(CertificateModel).where(
                CertificateModel.user_id == user_id,
                CertificateModel.event_id == event_id,
                CertificateModel.type == cert_type,
            )
        )
        m = res.scalar_one_or_none()
        if m is None:
            return None
        return {
            "id": str(m.id),
            "verification_code": m.verification_code,
            "pdf_url": m.pdf_url,
            "type": m.type,
        }

    async def set_pdf_url(self, cert_id: UUID, pdf_url: str) -> None:
        m = await self._s.get(CertificateModel, cert_id)
        if m:
            m.pdf_url = pdf_url
            await self._s.flush()

    async def get_by_code(self, code: str) -> dict | None:
        res = await self._s.execute(
            select(CertificateModel, EventModel, UserModel)
            .join(EventModel, CertificateModel.event_id == EventModel.id)
            .join(UserModel, CertificateModel.user_id == UserModel.id)
            .where(CertificateModel.verification_code == code)
        )
        row = res.first()
        if not row:
            return None
        cert, event, user = row
        return {
            "verification_code": cert.verification_code,
            "type": cert.type,
            "full_name": user.full_name,
            "event_title": event.title,
            "event_date": event.starts_at.isoformat() if event.starts_at else None,
            "generated_at": cert.generated_at.isoformat() if cert.generated_at else None,
            "valid": True,
        }

    async def list_by_user(self, user_id: UUID) -> list[dict]:
        res = await self._s.execute(
            select(CertificateModel, EventModel)
            .join(EventModel, CertificateModel.event_id == EventModel.id)
            .where(CertificateModel.user_id == user_id)
            .order_by(CertificateModel.generated_at.desc())
        )
        return [
            {
                "id": str(cert.id),
                "type": cert.type,
                "verification_code": cert.verification_code,
                "pdf_url": cert.pdf_url,
                "event_title": event.title,
                "generated_at": cert.generated_at.isoformat() if cert.generated_at else None,
            }
            for cert, event in res.all()
        ]
