from __future__ import annotations

from sqlmodel import Field

from .base import AppSchema, PaginatedResponse


class CustomerBase(AppSchema):
    cliente_nombre_comercial: str = ""
    cliente_nombre_fiscal: str = ""
    cliente_nombre_interno: str = ""
    cliente_abreviatura: str = ""
    cliente_cif: str = ""
    cliente_telefono: str = ""
    cliente_email: str = ""
    cliente_direccion: str = ""
    cliente_direccion_cp: str = ""
    cliente_direccion_localidad_id: str = ""
    cliente_direccion_municipio_id: str = ""
    cliente_direccion_provincia_id: str = ""
    cliente_direccion_isla_id: str = ""
    cliente_tipo: str = ""
    cliente_actividad: str = ""
    cliente_prospeccion: bool = False
    distribuidor_id: str = ""
    activo: bool = True


class CustomerListItem(CustomerBase):
    cliente_id: str
    cliente_codigo: int = 0


class CustomerDetail(CustomerListItem):
    pass


class CustomerListResponse(PaginatedResponse):
    items: list[CustomerListItem] = Field(default_factory=list)


class CustomerCreate(CustomerBase):
    cliente_id: str | None = None
    cliente_codigo: int | None = None


class CustomerUpdate(AppSchema):
    cliente_codigo: int | None = None
    cliente_nombre_comercial: str | None = None
    cliente_nombre_fiscal: str | None = None
    cliente_nombre_interno: str | None = None
    cliente_abreviatura: str | None = None
    cliente_cif: str | None = None
    cliente_telefono: str | None = None
    cliente_email: str | None = None
    cliente_direccion: str | None = None
    cliente_direccion_cp: str | None = None
    cliente_direccion_localidad_id: str | None = None
    cliente_direccion_municipio_id: str | None = None
    cliente_direccion_provincia_id: str | None = None
    cliente_direccion_isla_id: str | None = None
    cliente_tipo: str | None = None
    cliente_actividad: str | None = None
    cliente_prospeccion: bool | None = None
    distribuidor_id: str | None = None
    activo: bool | None = None


class AddressOption(AppSchema):
    id: str
    label: str
    parent_id: str = ""
    code: str = ""


class CustomerAddressCatalogsPayload(AppSchema):
    provincias: list[AddressOption] = Field(default_factory=list)
    islas: list[AddressOption] = Field(default_factory=list)
    municipios: list[AddressOption] = Field(default_factory=list)
    codigos_postales: list[AddressOption] = Field(default_factory=list)
    localidades: list[AddressOption] = Field(default_factory=list)


__all__ = [
    "AddressOption",
    "CustomerAddressCatalogsPayload",
    "CustomerBase",
    "CustomerCreate",
    "CustomerDetail",
    "CustomerListItem",
    "CustomerListResponse",
    "CustomerUpdate",
]
