from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_warehouse_inventory_service, get_warehouse_movement_service
from app.api.errors import bad_request, conflict
from app.api.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, MAX_PAGE_OFFSET
from app.schemas.warehouse import (
    InventoryAdjustmentPayload,
    InventoryDetailRead,
    InventoryExportPayload,
    InventoryHistoryListResponse,
    InventoryHeaderRead,
    WarehouseManualMovementCreate,
    WarehouseMovementListResponse,
    WarehouseMovementRead,
    WarehouseStockListResponse,
    WarehouseStockRead,
)
from app.services.warehouse_inventory_service import WarehouseInventoryService
from app.services.warehouse_movement_service import WarehouseMovementService, WarehouseStockConflictError


router = APIRouter(prefix="/warehouse", tags=["warehouse"])


@router.get("/stock", response_model=WarehouseStockListResponse)
def list_stock(
    almacen_id: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
    service: WarehouseInventoryService = Depends(get_warehouse_inventory_service),
) -> WarehouseStockListResponse:
    return service.stock_summary_payload(almacen_id, limit=limit, offset=offset)


@router.get("/movements", response_model=WarehouseMovementListResponse)
def list_movements(
    almacen_id: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
    service: WarehouseInventoryService = Depends(get_warehouse_inventory_service),
) -> WarehouseMovementListResponse:
    return service.movement_payload_serializable(almacen_id, limit=limit, offset=offset)


@router.post("/movements", response_model=WarehouseMovementRead, status_code=201)
def create_manual_movement(
    payload: WarehouseManualMovementCreate,
    service: WarehouseMovementService = Depends(get_warehouse_movement_service),
) -> WarehouseMovementRead:
    try:
        return service.create_manual_move_from_payload(payload)
    except WarehouseStockConflictError as exc:
        raise conflict(exc) from exc
    except ValueError as exc:
        raise bad_request(exc) from exc


@router.get("/inventory/history", response_model=InventoryHistoryListResponse)
def list_inventory_history(
    almacen_id: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
    service: WarehouseInventoryService = Depends(get_warehouse_inventory_service),
) -> InventoryHistoryListResponse:
    return service.history_payload(almacen_id, limit=limit, offset=offset)


@router.get("/inventory/export", response_model=InventoryExportPayload)
def inventory_export_payload(
    almacen_id: Annotated[str, Query(max_length=120)] = "",
    selected_id: Annotated[str, Query(max_length=120)] = "",
    service: WarehouseInventoryService = Depends(get_warehouse_inventory_service),
) -> InventoryExportPayload:
    return service.export_payload_serializable(almacen_id=almacen_id, selected_id=selected_id)


@router.post("/inventory/adjustments", response_model=InventoryHeaderRead, status_code=201)
def apply_inventory_adjustments(
    payload: InventoryAdjustmentPayload,
    service: WarehouseInventoryService = Depends(get_warehouse_inventory_service),
) -> InventoryHeaderRead:
    try:
        return service.apply_adjustments_from_payload(payload)
    except ValueError as exc:
        raise bad_request(exc) from exc


@router.get("/inventory/{inventory_id}", response_model=list[InventoryDetailRead])
def list_inventory_detail(
    inventory_id: str,
    service: WarehouseInventoryService = Depends(get_warehouse_inventory_service),
) -> list[InventoryDetailRead]:
    return service.history_detail_payload(inventory_id)
