from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_sales_annual_comparison_service
from app.schemas.sales import (
    SalesAnnualSummaryResponse,
    SalesAnnualSummaryRow,
    SalesFilterOption,
    SalesFilterOptionsResponse,
    SalesYearOption,
    SalesYearOptionsResponse,
)
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


@router.get("/annual-summary/years", response_model=SalesYearOptionsResponse)
def annual_summary_years(
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesYearOptionsResponse:
    years = service.list_years()
    return SalesYearOptionsResponse(
        items=[SalesYearOption(year=year, label=str(year)) for year in years],
    )


@router.get("/annual-summary/igsa/years", response_model=SalesYearOptionsResponse)
def annual_summary_igsa_years(
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesYearOptionsResponse:
    years = service.list_years_igsa()
    return SalesYearOptionsResponse(
        items=[SalesYearOption(year=year, label=str(year)) for year in years],
    )


@router.get("/annual-summary/filters/clients", response_model=SalesFilterOptionsResponse)
def annual_summary_clients(
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesFilterOptionsResponse:
    rows = service.list_filter_clients()
    return SalesFilterOptionsResponse(
        items=[
            SalesFilterOption(
                id=str(row.cliente_id or ""),
                name=str(row.cliente_nombre_comercial or row.cliente_nombre_fiscal or "").strip(),
                code=str(getattr(row, "cliente_codigo", "") or ""),
            )
            for row in rows
        ],
    )


@router.get("/annual-summary/filters/products", response_model=SalesFilterOptionsResponse)
def annual_summary_products(
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesFilterOptionsResponse:
    rows = service.list_filter_products()
    return SalesFilterOptionsResponse(
        items=[
            SalesFilterOption(
                id=str(row.articulo_id or ""),
                name=str(row.articulo_descripcion or "").strip(),
                code=str(row.articulo_referencia_corta or row.articulo_referencia or "").strip(),
            )
            for row in rows
        ],
    )


@router.get("/annual-summary/filters/manufacturers", response_model=SalesFilterOptionsResponse)
def annual_summary_manufacturers(
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesFilterOptionsResponse:
    rows = service.list_filter_manufacturers()
    return SalesFilterOptionsResponse(
        items=[
            SalesFilterOption(
                id=str(row.fabricante_id or ""),
                name=str(row.fabricante_nombre or "").strip(),
                code=str(getattr(row, "fabricante_codigo", "") or ""),
            )
            for row in rows
        ],
    )


@router.get("/annual-summary/igsa/filters/manufacturers", response_model=SalesFilterOptionsResponse)
def annual_summary_igsa_manufacturers(
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesFilterOptionsResponse:
    rows = service.list_filter_manufacturers_igsa()
    return SalesFilterOptionsResponse(
        items=[
            SalesFilterOption(
                id=str(row.fabricante_id or ""),
                name=str(row.fabricante_nombre or "").strip(),
                code=str(getattr(row, "fabricante_codigo", "") or ""),
            )
            for row in rows
        ],
    )


@router.get("/annual-summary/filters/families", response_model=SalesFilterOptionsResponse)
def annual_summary_families(
    fabricante_id: Annotated[str, Query(max_length=120)] = "",
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesFilterOptionsResponse:
    rows = service.list_filter_families(fabricante_id=fabricante_id)
    return SalesFilterOptionsResponse(
        items=[
            SalesFilterOption(
                id=str(row.articulo_familia_id or ""),
                name=str(row.articulo_familia_nombre or "").strip(),
                code=str(row.articulo_familia_codigo or "").strip(),
                parent_id=str(row.fabricante_id or ""),
            )
            for row in rows
        ],
    )


@router.get("/annual-summary/igsa/filters/families", response_model=SalesFilterOptionsResponse)
def annual_summary_igsa_families(
    fabricante_id: Annotated[str, Query(max_length=120)] = "",
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesFilterOptionsResponse:
    rows = service.list_filter_families_igsa(fabricante_id=fabricante_id)
    return SalesFilterOptionsResponse(
        items=[
            SalesFilterOption(
                id=str(row.articulo_familia_id or ""),
                name=str(row.articulo_familia_nombre or "").strip(),
                code=str(row.articulo_familia_codigo or "").strip(),
                parent_id=str(row.fabricante_id or ""),
            )
            for row in rows
        ],
    )


@router.get("/annual-summary/filters/subfamilies", response_model=SalesFilterOptionsResponse)
def annual_summary_subfamilies(
    familia_id: Annotated[str, Query(max_length=120)] = "",
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesFilterOptionsResponse:
    rows = service.list_filter_subfamilies(familia_id=familia_id)
    return SalesFilterOptionsResponse(
        items=[
            SalesFilterOption(
                id=str(row.articulo_subfamilia_id or ""),
                name=str(row.articulo_subfamilia_nombre or "").strip(),
                code=str(row.articulo_subfamilia_codigo or "").strip(),
                parent_id=str(row.articulo_familia_id or ""),
            )
            for row in rows
        ],
    )


@router.get("/annual-summary/igsa/filters/subfamilies", response_model=SalesFilterOptionsResponse)
def annual_summary_igsa_subfamilies(
    familia_id: Annotated[str, Query(max_length=120)] = "",
    service: SalesAnnualComparisonService = Depends(get_sales_annual_comparison_service),
) -> SalesFilterOptionsResponse:
    rows = service.list_filter_subfamilies_igsa(familia_id=familia_id)
    return SalesFilterOptionsResponse(
        items=[
            SalesFilterOption(
                id=str(row.articulo_subfamilia_id or ""),
                name=str(row.articulo_subfamilia_nombre or "").strip(),
                code=str(row.articulo_subfamilia_codigo or "").strip(),
                parent_id=str(row.articulo_familia_id or ""),
            )
            for row in rows
        ],
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
