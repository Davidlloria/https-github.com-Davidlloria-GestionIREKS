from __future__ import annotations

from datetime import datetime

from sqlmodel import Field

from .base import AppSchema, PaginatedResponse


class ContactBase(AppSchema):
    cliente_id: str
    nombre: str = ""
    apellidos: str = ""
    cargo: str = ""
    nif: str = ""
    telefono: str = ""
    email: str = ""


class ContactListItem(ContactBase):
    contacto_id: str
    contacto_codigo: int = 0
    cliente_nombre: str = ""


class ContactDetail(ContactListItem):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContactListResponse(PaginatedResponse):
    items: list[ContactListItem] = Field(default_factory=list)


class ContactCreate(ContactBase):
    contacto_id: str | None = None
    contacto_codigo: int | None = None


class ContactUpdate(AppSchema):
    contacto_codigo: int | None = None
    cliente_id: str | None = None
    nombre: str | None = None
    apellidos: str | None = None
    cargo: str | None = None
    nif: str | None = None
    telefono: str | None = None
    email: str | None = None


class ContactCompanyOption(AppSchema):
    cliente_id: str
    nombre: str


__all__ = [
    "ContactBase",
    "ContactCompanyOption",
    "ContactCreate",
    "ContactDetail",
    "ContactListItem",
    "ContactListResponse",
    "ContactUpdate",
]
