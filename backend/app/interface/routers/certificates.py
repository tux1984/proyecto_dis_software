"""CertificateRouter — emisión, descarga y verificación (RF-13/21, RN-05)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.application.certificate_service import CertificateService
from app.domain.errors import ValidationError
from app.infrastructure.pdf import STORAGE_DIR
from app.interface.deps import CurrentUser, get_certificate_service, get_current_user, require_role
from app.interface.schemas import CertificateRequest

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.post("/{event_id}/request")
async def request_certificate(
    event_id: UUID,
    body: CertificateRequest,
    user: CurrentUser = Depends(get_current_user),
    service: CertificateService = Depends(get_certificate_service),
) -> dict:
    return await service.request_certificate(user.id, event_id, body.cert_type)


@router.post("/{event_id}/batch", status_code=202)
async def batch(
    event_id: UUID,
    body: CertificateRequest,
    user: CurrentUser = Depends(require_role("organizer")),
    service: CertificateService = Depends(get_certificate_service),
) -> dict:
    return await service.generate_batch(event_id, user.id, body.cert_type)


@router.get("/mine")
async def my_certificates(
    user: CurrentUser = Depends(get_current_user),
    service: CertificateService = Depends(get_certificate_service),
) -> dict:
    return {"certificates": await service.list_mine(user.id)}


@router.get("/verify/{code}")
async def verify(
    code: str, service: CertificateService = Depends(get_certificate_service)
) -> dict:
    # Verificación pública del código único (RF-21).
    return await service.verify(code)


@router.get("/file/{filename}")
async def download_file(filename: str) -> FileResponse:
    # Sirve el PDF generado por el worker (validando contra path traversal).
    safe = Path(filename).name
    path = STORAGE_DIR / safe
    if not path.exists():
        raise ValidationError("Certificado aún no generado")
    return FileResponse(str(path), media_type="application/pdf", filename=safe)
