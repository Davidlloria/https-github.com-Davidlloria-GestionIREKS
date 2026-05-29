from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.deps import get_api_settings_service, get_settings_import_service, get_settings_maintenance_service
from app.api.errors import bad_request, not_found
from app.schemas.orders import OrderJsonImportResponse
from app.schemas.settings import (
    ApiSettingsPayload,
    DocumentImportRequest,
    MaintenanceBackupRequest,
    MaintenanceResult,
    MaintenanceStatus,
)
from app.schemas.warehouse import WarehouseOption
from app.services.api_settings_service import ApiSettingsService
from app.services.settings_import_service import SettingsImportService
from app.services.settings_maintenance_service import SettingsMaintenanceService


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/maintenance/status", response_model=MaintenanceStatus)
def maintenance_status(
    service: SettingsMaintenanceService = Depends(get_settings_maintenance_service),
) -> MaintenanceStatus:
    return MaintenanceStatus.model_validate(service.database_status())


@router.post("/maintenance/integrity-check", response_model=MaintenanceResult)
def run_integrity_check(
    service: SettingsMaintenanceService = Depends(get_settings_maintenance_service),
) -> MaintenanceResult:
    messages = service.run_integrity_check()
    ok = all(str(message).strip().lower() == "ok" for message in messages)
    return MaintenanceResult(
        ok=ok,
        message="Comprobacion de integridad completada.",
        details={"messages": messages},
    )


@router.post("/maintenance/repair-contact-links", response_model=MaintenanceResult)
def repair_contact_links(
    service: SettingsMaintenanceService = Depends(get_settings_maintenance_service),
) -> MaintenanceResult:
    details = service.repair_contact_links()
    return MaintenanceResult(ok=True, message="Enlaces de contactos revisados.", details=details)


@router.post("/maintenance/create-missing-contact-clients", response_model=MaintenanceResult)
def create_missing_contact_clients(
    service: SettingsMaintenanceService = Depends(get_settings_maintenance_service),
) -> MaintenanceResult:
    created = service.create_missing_clients_for_contact_links()
    return MaintenanceResult(
        ok=True,
        message="Clientes faltantes creados.",
        details={"created": created},
    )


@router.post("/maintenance/optimize", response_model=MaintenanceResult)
def optimize_database(
    service: SettingsMaintenanceService = Depends(get_settings_maintenance_service),
) -> MaintenanceResult:
    service.optimize_database()
    return MaintenanceResult(ok=True, message="Base de datos optimizada.")


@router.post("/maintenance/backup", response_model=MaintenanceResult)
def backup_database(
    payload: MaintenanceBackupRequest,
    service: SettingsMaintenanceService = Depends(get_settings_maintenance_service),
) -> MaintenanceResult:
    destination_path = str(payload.destination_path or "").strip()
    if not destination_path:
        raise bad_request("Indica destination_path.")
    destination = service.backup_database(Path(destination_path))
    return MaintenanceResult(
        ok=True,
        message="Copia de seguridad creada.",
        details={"path": str(destination)},
    )


@router.get("/api/{provider}", response_model=ApiSettingsPayload)
def get_api_settings(
    provider: str,
    service: ApiSettingsService = Depends(get_api_settings_service),
) -> ApiSettingsPayload:
    try:
        return ApiSettingsPayload.model_validate(service.provider_payload(provider))
    except ValueError as exc:
        raise not_found(exc) from exc


@router.put("/api/{provider}", response_model=ApiSettingsPayload)
def save_api_settings(
    provider: str,
    payload: ApiSettingsPayload,
    service: ApiSettingsService = Depends(get_api_settings_service),
) -> ApiSettingsPayload:
    try:
        return ApiSettingsPayload.model_validate(service.save_provider(provider, payload.config))
    except ValueError as exc:
        raise not_found(exc) from exc


@router.get("/imports/warehouses", response_model=list[WarehouseOption])
def list_import_warehouses(
    service: SettingsImportService = Depends(get_settings_import_service),
) -> list[WarehouseOption]:
    return [
        WarehouseOption(almacen_id=str(option.value or ""), almacen_nombre=str(option.label or ""))
        for option in service.warehouse_filter_options()
    ]


@router.post("/imports/orders-json", response_model=OrderJsonImportResponse)
def import_order_json(
    payload: DocumentImportRequest,
    service: SettingsImportService = Depends(get_settings_import_service),
) -> OrderJsonImportResponse:
    try:
        result = service.import_order_json(Path(payload.file_path), payload.almacen_id)
    except ValueError as exc:
        raise bad_request(exc) from exc
    return OrderJsonImportResponse.model_validate(result, from_attributes=True)
