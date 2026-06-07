from __future__ import annotations

from typing import Literal

from sqlmodel import Field

from .base import AppSchema


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
    source: Literal["ireks", "igsa"] = "ireks"
    year: int = 0
    month: int = 0
    acumulado: bool = False
    total: int = 0
    items: list[SalesAnnualSummaryRow] = Field(default_factory=list)


__all__ = [
    "SalesAnnualSummaryResponse",
    "SalesAnnualSummaryRow",
]
