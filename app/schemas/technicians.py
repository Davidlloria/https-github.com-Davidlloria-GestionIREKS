from __future__ import annotations

from datetime import datetime

from sqlmodel import Field

from .base import AppSchema, PaginatedResponse


class TechnicianBase(AppSchema):
    nombre: str = ""
    apellidos: str = ""
    movil: str = ""
    interno: str = ""
    email: str = ""


class TechnicianListItem(TechnicianBase):
    tecnico_id: str
    tecnico_codigo: int = 0


class TechnicianDetail(TechnicianListItem):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TechnicianListResponse(PaginatedResponse):
    items: list[TechnicianListItem] = Field(default_factory=list)


__all__ = [
    "TechnicianBase",
    "TechnicianDetail",
    "TechnicianListItem",
    "TechnicianListResponse",
]
