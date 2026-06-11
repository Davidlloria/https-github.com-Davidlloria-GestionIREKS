from __future__ import annotations

from sqlmodel import Field

from .base import AppSchema, PaginatedResponse


class DistributorBase(AppSchema):
    distribuidor_codigo: int = 0
    distribuidor_razon_social: str = ""
    distribuidor_nombre_comercial: str = ""
    distribuidor_cif: str = ""
    distribuidor_telefono: str = ""
    distribuidor_contacto: str = ""


class DistributorListItem(DistributorBase):
    distribuidor_id: str


class DistributorDetail(DistributorListItem):
    pass


class DistributorListResponse(PaginatedResponse):
    items: list[DistributorListItem] = Field(default_factory=list)


__all__ = [
    "DistributorBase",
    "DistributorDetail",
    "DistributorListItem",
    "DistributorListResponse",
]
