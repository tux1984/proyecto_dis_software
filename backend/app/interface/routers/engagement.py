"""Participación: ponentes, asistencia, evaluación y material (RF-10/18/19/20/22)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.application.engagement_service import (
    AttendanceService,
    EvaluationService,
    MaterialService,
    SpeakerService,
)
from app.interface.deps import (
    CurrentUser,
    get_attendance_service,
    get_current_user,
    get_evaluation_service,
    get_material_service,
    get_speaker_service,
    require_role,
)
from app.interface.schemas import (
    AttendanceRecord,
    EvaluationSubmit,
    SpeakerInvite,
    SpeakerRespond,
)

router = APIRouter(tags=["engagement"])


# ---- Ponentes (RF-10, RF-22) ----
@router.post("/events/{event_id}/speakers", status_code=201)
async def invite_speaker(
    event_id: UUID,
    body: SpeakerInvite,
    user: CurrentUser = Depends(require_role("organizer")),
    service: SpeakerService = Depends(get_speaker_service),
) -> dict:
    return await service.invite(event_id, user.id, str(body.email))


@router.post("/speakers/respond")
async def respond_invitation(
    token: str,
    body: SpeakerRespond,
    service: SpeakerService = Depends(get_speaker_service),
) -> dict:
    # Token de un solo uso; si ya se usó, el servicio lanza ValidationError -> 400.
    return await service.respond(token, body.accept, body.bio, body.material_url)


@router.get("/events/{event_id}/speakers")
async def list_speakers(
    event_id: UUID, service: SpeakerService = Depends(get_speaker_service)
) -> dict:
    return {"speakers": await service.list_confirmed(event_id)}


# ---- Asistencia (RF-19, RN-05) ----
@router.post("/events/{event_id}/attendance", status_code=201)
async def record_attendance(
    event_id: UUID,
    body: AttendanceRecord,
    user: CurrentUser = Depends(require_role("organizer")),
    service: AttendanceService = Depends(get_attendance_service),
) -> dict:
    return await service.record(event_id, user.id, body.user_id, body.session_id)


# ---- Material (RF-18, RN-09) ----
@router.get("/events/{event_id}/material")
async def get_material(
    event_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    return await service.get_material(event_id, user.id)


# ---- Evaluación post-evento (RF-20) ----
@router.post("/events/{event_id}/evaluation", status_code=201)
async def submit_evaluation(
    event_id: UUID,
    body: EvaluationSubmit,
    user: CurrentUser = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> dict:
    return await service.submit(event_id, user.id, body.payload)
