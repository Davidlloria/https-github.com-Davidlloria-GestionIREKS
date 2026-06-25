from __future__ import annotations

from typing import Literal

from sqlmodel import Field

from .base import AppSchema


class SalesYearOption(AppSchema):
    year: int = 0
    label: str = ""


class SalesYearOptionsResponse(AppSchema):
    items: list[SalesYearOption] = Field(default_factory=list)


class SalesFilterOption(AppSchema):
    id: str = ""
    name: str = ""
    code: str = ""
    parent_id: str = ""


class SalesFilterOptionsResponse(AppSchema):
    items: list[SalesFilterOption] = Field(default_factory=list)


class SalesAnnualSummaryRow(AppSchema):
    articulo_id: str = ""
    fabricante_id: str = ""
    familia_id: str = ""
    subfamilia_id: str = ""
    codigo: str = ""
    nombre: str = ""
    kilos_prev: float = 0.0
    sc_prev: float = 0.0
    ventas_prev: float = 0.0
    kilos_curr: float = 0.0
    sc_curr: float = 0.0
    ventas_curr: float = 0.0
    delta_kg: float = 0.0
    delta_kg_pct: float = 0.0
    delta_ventas: float = 0.0
    delta_ventas_pct: float = 0.0


class SalesAnnualSummaryResponse(AppSchema):
    source: Literal["ireks", "igsa", "clientes"] = "ireks"
    year: int = 0
    month: int = 0
    acumulado: bool = False
    total: int = 0
    items: list[SalesAnnualSummaryRow] = Field(default_factory=list)


class SalesClientsAnnualSummaryRow(AppSchema):
    articulo_id: str = ""
    fabricante_id: str = ""
    familia_id: str = ""
    subfamilia_id: str = ""
    codigo: str = ""
    nombre: str = ""
    unidades_prev: float = 0.0
    kg_prev: float = 0.0
    euros_prev: float = 0.0
    unidades_curr: float = 0.0
    kg_curr: float = 0.0
    euros_curr: float = 0.0
    delta_unidades: float = 0.0
    delta_unidades_pct: float = 0.0
    delta_kg: float = 0.0
    delta_kg_pct: float = 0.0
    delta_euros: float = 0.0
    delta_euros_pct: float = 0.0


class SalesClientsAnnualSummaryResponse(AppSchema):
    source: Literal["clientes"] = "clientes"
    year: int = 0
    total: int = 0
    items: list[SalesClientsAnnualSummaryRow] = Field(default_factory=list)


class SalesImportResponse(AppSchema):
    ok: bool = True
    message: str = ""
    imported: int = 0
    incidencias: int = 0


__all__ = [
    "SalesFilterOption",
    "SalesFilterOptionsResponse",
    "SalesAnnualSummaryResponse",
    "SalesAnnualSummaryRow",
    "SalesClientsAnnualSummaryResponse",
    "SalesClientsAnnualSummaryRow",
    "SalesImportResponse",
    "SalesYearOption",
    "SalesYearOptionsResponse",
]
