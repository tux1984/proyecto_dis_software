"""Metadatos públicos del catálogo (categorías) — RF-27.

Las categorías son gestionables por el administrador (POST en /admin/categories)
y consultables públicamente para poblar filtros y formularios de creación.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.infrastructure.repositories.support_repository import CategoryRepository
from app.interface.deps import get_category_repository

router = APIRouter(tags=["meta"])


@router.get("/categories")
async def list_categories(
    categories: CategoryRepository = Depends(get_category_repository),
) -> dict:
    return {"categories": await categories.list_all()}
