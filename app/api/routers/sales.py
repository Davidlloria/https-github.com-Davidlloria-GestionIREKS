from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_sales_annual_comparison_service
from app.schemas.sales import SalesAnnualSummaryResponse, SalesAnnualSummaryRow
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService


router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/annual-summary", response_model=SalesAnnualSummaryResponse)
def annual_summary(
    year: Annotated[int, Query(ge=1)],
    month: Annotated[int, Query(ge=0, le=12)] = 0,
    acumulado: bool = False,
    cliente_id: Annotated[str, Query(max_length=120)] = "",
    articulo_id: Annotated[str, Query(max_length=120)] = "",
    producto_texto: Annotated[str, Query(max_length=120)] = "",
    fabricante_id: Annotated[str, Query(max_length=120)] = "",
    familia_id: Annotated[str, Query(max_length=120)] = "",
    subfamilia_id: Annotated[str, Query(max_length=120)] = "",
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesAnnualSummaryResponse:
    rows = service.listar_resumen_anual(
        year=year,
        month=month,
        acumulado=acumulado,
        cliente_id=cliente_id,
        articulo_id=articulo_id,
        producto_texto=producto_texto,
        fabricante_id=fabricante_id,
        familia_id=familia_id,
        subfamilia_id=subfamilia_id,
    )
    return SalesAnnualSummaryResponse(
        source="ireks",
        year=year,
        month=month,
        acumulado=acumulado,
        total=len(rows),
        items=[SalesAnnualSummaryRow.model_validate(row, from_attributes=True) for row in rows],
    )


@router.get("/annual-summary/igsa", response_model=SalesAnnualSummaryResponse)
def annual_summary_igsa(
    year: Annotated[int, Query(ge=1)],
    month: Annotated[int, Query(ge=0, le=12)] = 0,
    acumulado: bool = False,
    producto_texto: Annotated[str, Query(max_length=120)] = "",
    fabricante_id: Annotated[str, Query(max_length=120)] = "",
    familia_id: Annotated[str, Query(max_length=120)] = "",
    subfamilia_id: Annotated[str, Query(max_length=120)] = "",
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesAnnualSummaryResponse:
    rows = service.listar_resumen_anual_igsa(
        year=year,
        month=month,
        acumulado=acumulado,
        producto_texto=producto_texto,
        fabricante_id=fabricante_id,
        familia_id=familia_id,
        subfamilia_id=subfamilia_id,
    )
    return SalesAnnualSummaryResponse(
        source="igsa",
        year=year,
        month=month,
        acumulado=acumulado,
        total=len(rows),
        items=[SalesAnnualSummaryRow.model_validate(row, from_attributes=True) for row in rows],
    )
