from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_order_document_import_service, get_order_query_service, get_order_service
from app.api.errors import bad_request, conflict, not_found
from app.api.paths import input_file_path
from app.api.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, MAX_PAGE_OFFSET
from app.schemas.orders import (
    OrderCreate,
    OrderDocumentImportPayload,
    OrderDocumentImportResponse,
    OrderItemRead,
    OrderJsonImportPayload,
    OrderJsonImportResponse,
    OrderLineWrite,
    OrderListItem,
    OrderPendingRead,
    OrderRead,
    OrderUpdate,
)
from app.services.order_document_import_service import OrderDocumentImportService, OrderNotFoundError
from app.services.order_query_service import OrderQueryService
from app.services.order_service import OrderService


router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderListItem])
def list_orders(
    year: Annotated[str, Query(max_length=4)] = "",
    month_from: Annotated[int, Query(ge=0, le=12)] = 0,
    month_to: Annotated[int, Query(ge=0, le=12)] = 0,
    almacen_id: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
    service: OrderQueryService = Depends(get_order_query_service),
) -> list[OrderListItem]:
    return service.list_order_payloads(
        year_filter=year,
        month_from=month_from,
        month_to=month_to,
        almacen_filter=almacen_id,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    service: OrderService = Depends(get_order_service),
) -> OrderRead:
    try:
        return service.create_from_payload(payload)
    except ValueError as exc:
        raise bad_request(exc) from exc


@router.post("/import/json", response_model=OrderJsonImportResponse)
def import_order_json(
    payload: OrderJsonImportPayload,
    service: OrderService = Depends(get_order_service),
) -> OrderJsonImportResponse:
    source = input_file_path(payload.source_path, field_name="source_path", allowed_suffixes={".json"})
    try:
        result = service.import_order_json(source, payload.almacen_id)
    except ValueError as exc:
        raise bad_request(exc) from exc
    return OrderJsonImportResponse.model_validate(result, from_attributes=True)


@router.post("/{order_id}/import/albaran-pdf", response_model=OrderDocumentImportResponse)
def import_albaran_pdf(
    order_id: str,
    payload: OrderDocumentImportPayload,
    service: OrderDocumentImportService = Depends(get_order_document_import_service),
) -> OrderDocumentImportResponse:
    source = input_file_path(payload.source_path, field_name="source_path", allowed_suffixes={".pdf"})
    try:
        result = service.import_albaran_pdf(order_id, source)
    except OrderNotFoundError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise bad_request(exc) from exc
    return OrderDocumentImportResponse.model_validate(result, from_attributes=True)


@router.post("/{order_id}/import/factura-pdf", response_model=OrderDocumentImportResponse)
def import_factura_pdf(
    order_id: str,
    payload: OrderDocumentImportPayload,
    service: OrderDocumentImportService = Depends(get_order_document_import_service),
) -> OrderDocumentImportResponse:
    source = input_file_path(payload.source_path, field_name="source_path", allowed_suffixes={".pdf"})
    try:
        result = service.import_factura_pdf(order_id, source)
    except OrderNotFoundError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise bad_request(exc) from exc
    return OrderDocumentImportResponse.model_validate(result, from_attributes=True)


@router.patch("/{order_id}", response_model=OrderRead)
def update_order(
    order_id: str,
    payload: OrderUpdate,
    service: OrderService = Depends(get_order_service),
) -> OrderRead:
    try:
        return service.update_from_payload(order_id, payload)
    except ValueError as exc:
        raise not_found(exc) from exc


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(
    order_id: str,
    service: OrderService = Depends(get_order_service),
) -> Response:
    try:
        if not service.delete_order_if_exists(order_id):
            raise not_found("Pedido no encontrado.")
    except IntegrityError as exc:
        raise conflict("No se puede eliminar el pedido porque tiene dependencias.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{order_id}", response_model=OrderRead)
def get_order(
    order_id: str,
    service: OrderQueryService = Depends(get_order_query_service),
) -> OrderRead:
    payload = service.detail_payload(order_id)
    if payload is None:
        raise not_found("Pedido no encontrado.")
    return payload


@router.get("/{order_id}/items", response_model=list[OrderItemRead])
def list_order_items(
    order_id: str,
    service: OrderQueryService = Depends(get_order_query_service),
) -> list[OrderItemRead]:
    return service.list_order_items_payload(order_id)


@router.post("/{order_id}/items", response_model=OrderItemRead, status_code=status.HTTP_201_CREATED)
def create_order_item(
    order_id: str,
    payload: OrderLineWrite,
    service: OrderService = Depends(get_order_service),
) -> OrderItemRead:
    try:
        return service.add_order_line_from_payload(order_id, payload)
    except ValueError as exc:
        raise not_found(exc) from exc


@router.patch("/items/{item_id}", response_model=OrderItemRead)
def update_order_item(
    item_id: str,
    payload: OrderLineWrite,
    service: OrderService = Depends(get_order_service),
) -> OrderItemRead:
    try:
        return service.update_order_line_from_payload(item_id, payload)
    except ValueError as exc:
        raise not_found(exc) from exc


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order_item(
    item_id: str,
    service: OrderService = Depends(get_order_service),
) -> Response:
    if not service.delete_order_line_if_exists(item_id):
        raise not_found("Linea de pedido no encontrada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{order_id}/pending", response_model=list[OrderPendingRead])
def list_order_pending(
    order_id: str,
    service: OrderQueryService = Depends(get_order_query_service),
) -> list[OrderPendingRead]:
    return service.list_pendientes_payload(order_id)
