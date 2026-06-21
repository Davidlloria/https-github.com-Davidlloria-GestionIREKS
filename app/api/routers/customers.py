from __future__ import annotations

from typing import Annotated

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_customer_service
from app.api.errors import bad_request, conflict, not_found
from app.api.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, MAX_PAGE_OFFSET
from app.schemas.customers import (
    CustomerAddressCatalogsPayload,
    CustomerCreate,
    CustomerDetail,
    CustomerListingRequest,
    CustomerListingPdfExportRequest,
    CustomerListingResponse,
    CustomerListingXlsxExportRequest,
    CustomerListResponse,
    CustomerUpdate,
)
from app.api.deps import get_customer_report_flow_service
from app.services.customer_report_flow_service import CustomerReportFlowService
from app.services.customer_service import CustomerService
from app.services.report_export_service import ReportExportService


router = APIRouter(prefix="/customers", tags=["customers"])
report_export_service = ReportExportService()


@router.get("", response_model=CustomerListResponse)
def list_customers(
    q: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerListResponse:
    return service.list_payload(q, limit=limit, offset=offset)


@router.get("/address-catalogs", response_model=CustomerAddressCatalogsPayload)
def address_catalogs(
    service: CustomerService = Depends(get_customer_service),
) -> CustomerAddressCatalogsPayload:
    return service.address_catalogs_payload()


@router.post("/listings", response_model=CustomerListingResponse)
def generate_listing(
    payload: CustomerListingRequest,
    service: CustomerReportFlowService = Depends(get_customer_report_flow_service),
) -> CustomerListingResponse:
    result = service.generate_report(payload.prompt)
    report = result.report
    if report is None:
        return CustomerListingResponse(
            status=result.status,
            message=result.message,
            title="",
            headers=[],
            rows=[],
            source=result.source,
            used_ai=result.used_ai,
        )
    return CustomerListingResponse(
        status=result.status,
        message=result.message,
        title=report.title,
        headers=report.headers,
        rows=report.rows,
        source=result.source,
        used_ai=result.used_ai,
    )


@router.post(
    "/listings/pdf",
    responses={200: {"content": {"application/pdf": {}}}},
)
def export_listing_pdf(
    payload: CustomerListingPdfExportRequest,
) -> FileResponse:
    path = report_export_service.default_path(payload.title or "Listado de clientes", "pdf")
    report_export_service.export_pdf(path, payload.title or "Listado de clientes", payload.headers, payload.rows)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=Path(path).name,
        headers={"Content-Disposition": f'attachment; filename="{Path(path).name}"'},
    )


@router.post(
    "/listings/xlsx",
    responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}},
)
def export_listing_xlsx(
    payload: CustomerListingXlsxExportRequest,
) -> FileResponse:
    path = report_export_service.default_path(payload.title or "Listado de clientes", "xlsx")
    report_export_service.export_excel(path, payload.title or "Listado de clientes", payload.headers, payload.rows)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(path).name,
        headers={"Content-Disposition": f'attachment; filename="{Path(path).name}"'},
    )


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(
    customer_id: str,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerDetail:
    payload = service.detail_payload(customer_id)
    if payload is None:
        raise not_found("Cliente no encontrado.")
    return payload


@router.post("", response_model=CustomerDetail, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerDetail:
    try:
        return service.create_from_payload(payload)
    except IntegrityError as exc:
        raise conflict("No se puede crear el cliente porque ya existe o entra en conflicto con datos unicos.") from exc
    except ValueError as exc:
        raise bad_request(exc) from exc


@router.patch("/{customer_id}", response_model=CustomerDetail)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerDetail:
    try:
        return service.update_from_payload(customer_id, payload)
    except IntegrityError as exc:
        raise conflict("No se puede actualizar el cliente porque entra en conflicto con datos unicos.") from exc
    except ValueError as exc:
        raise not_found(exc) from exc


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: str,
    service: CustomerService = Depends(get_customer_service),
) -> Response:
    blockers = service.delete_blockers(customer_id)
    if blockers:
        raise conflict(f"No se puede eliminar el cliente porque tiene dependencias: {', '.join(blockers)}.")
    try:
        deleted = service.delete(customer_id)
    except IntegrityError as exc:
        raise conflict("No se puede eliminar el cliente porque tiene dependencias.") from exc
    if not deleted:
        raise not_found("Cliente no encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
