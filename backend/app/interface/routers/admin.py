"""AdminRouter — supervisión institucional, RBAC, auditoría (RF-24/25/26/29)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.application.admin_service import AdminService
from app.infrastructure.repositories.support_repository import CategoryRepository
from app.interface.deps import (
    CurrentUser,
    get_admin_service,
    get_category_repository,
    require_role,
)
from app.interface.schemas import CategoryCreate, RoleChange

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
async def institutional_dashboard(
    _: CurrentUser = Depends(require_role("admin")),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    return await service.institutional_dashboard()


@router.get("/events/pending")
async def pending_events(
    _: CurrentUser = Depends(require_role("admin")),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    return {"events": await service.list_pending_events()}


@router.get("/users")
async def list_users(
    _: CurrentUser = Depends(require_role("admin")),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    return {"users": await service.list_users()}


@router.post("/users/{user_id}/role")
async def change_role(
    user_id: UUID,
    body: RoleChange,
    admin: CurrentUser = Depends(require_role("admin")),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    return await service.set_role(admin.id, user_id, body.role)


@router.get("/audit")
async def query_audit(
    action: str | None = None,
    limit: int = Query(default=100, le=500),
    _: CurrentUser = Depends(require_role("admin")),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    return {"entries": await service.query_audit(action=action, limit=limit)}


@router.get("/pii-access")
async def pii_access_log(
    _: CurrentUser = Depends(require_role("admin")),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    return {"entries": await service.pii_access_log()}


@router.post("/categories", status_code=201)
async def create_category(
    body: CategoryCreate,
    _: CurrentUser = Depends(require_role("admin")),
    categories: CategoryRepository = Depends(get_category_repository),
) -> dict:
    cid = await categories.create(body.name, body.faculty)
    return {"id": str(cid), "name": body.name}
