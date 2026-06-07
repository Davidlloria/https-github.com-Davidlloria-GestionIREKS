from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from app.services.warehouse_inventory_adjustment_preparation_service import (
    WarehouseInventoryAdjustmentPreparationResult,
    WarehouseInventoryAdjustmentPreparationService,
    WarehouseInventoryAdjustmentRowInput,
)
from app.services.warehouse_inventory_service import WarehouseInventoryService


@dataclass
class WarehouseInventoryAdjustmentFlowResult:
    status: str
    message: str = ""
    pending: list[dict[str, Any]] = field(default_factory=list)
    inventory_code: str = ""
    prepared_count: int = 0
    applied_count: int = 0
    contador: str = ""
    aprobador: str = ""


class WarehouseInventoryAdjustmentFlowService:
    def __init__(
        self,
        *,
        preparation_service: WarehouseInventoryAdjustmentPreparationService | None = None,
        inventory_service: WarehouseInventoryService | None = None,
    ) -> None:
        self.preparation_service = preparation_service or WarehouseInventoryAdjustmentPreparationService()
        self.inventory_service = inventory_service or WarehouseInventoryService()

    def build_row_inputs(
        self,
        rows: Iterable[WarehouseInventoryAdjustmentRowInput | dict[str, Any]],
    ) -> list[WarehouseInventoryAdjustmentRowInput]:
        return [self._normalize_row(row) for row in rows]

    def prepare_adjustments(
        self,
        rows: Iterable[WarehouseInventoryAdjustmentRowInput | dict[str, Any]],
        *,
        almacen_id: str,
        today: date | None = None,
    ) -> WarehouseInventoryAdjustmentFlowResult:
        prepared = self.preparation_service.prepare_adjustments(
            self.build_row_inputs(rows),
            almacen_id=almacen_id,
            today=today,
        )
        return self._from_preparation(prepared)

    def apply_adjustments(
        self,
        preparation: WarehouseInventoryAdjustmentFlowResult,
        *,
        almacen_id: str,
        contador: str,
        aprobador: str,
    ) -> WarehouseInventoryAdjustmentFlowResult:
        validation = self.validate_application(preparation, contador=contador, aprobador=aprobador)
        if validation.status != "ready":
            return validation
        clean_contador = validation.contador
        clean_aprobador = validation.aprobador
        try:
            applied = self.inventory_service.apply_adjustments(
                pending=list(preparation.pending),
                almacen_id=str(almacen_id or "").strip(),
                contador=clean_contador,
                aprobador=clean_aprobador,
            )
        except Exception as exc:  # noqa: BLE001
            return WarehouseInventoryAdjustmentFlowResult(
                status="error",
                message=str(exc),
                pending=list(preparation.pending),
                inventory_code=preparation.inventory_code,
                prepared_count=preparation.prepared_count,
                contador=clean_contador,
                aprobador=clean_aprobador,
            )
        return WarehouseInventoryAdjustmentFlowResult(
            status="success",
            message=f"Ajustes aplicados: {applied}",
            pending=[],
            inventory_code=preparation.inventory_code,
            prepared_count=preparation.prepared_count,
            applied_count=int(applied or 0),
            contador=clean_contador,
            aprobador=clean_aprobador,
        )

    def validate_application(
        self,
        preparation: WarehouseInventoryAdjustmentFlowResult,
        *,
        contador: str,
        aprobador: str,
    ) -> WarehouseInventoryAdjustmentFlowResult:
        if preparation.status != "ready" or not preparation.pending:
            return WarehouseInventoryAdjustmentFlowResult(
                status="no_differences",
                message=preparation.message or "No hay ajustes preparados. Pulsa 'Preparar ajustes'.",
                inventory_code=preparation.inventory_code,
                prepared_count=preparation.prepared_count,
            )
        clean_contador = str(contador or "").strip()
        clean_aprobador = str(aprobador or "").strip()
        if not clean_contador or not clean_aprobador:
            return WarehouseInventoryAdjustmentFlowResult(
                status="invalid_approval",
                message="Indica Contador y Aprobador antes de aplicar.",
                pending=list(preparation.pending),
                inventory_code=preparation.inventory_code,
                prepared_count=preparation.prepared_count,
            )
        return WarehouseInventoryAdjustmentFlowResult(
            status="ready",
            message=preparation.message,
            pending=list(preparation.pending),
            inventory_code=preparation.inventory_code,
            prepared_count=preparation.prepared_count,
            contador=clean_contador,
            aprobador=clean_aprobador,
        )

    @staticmethod
    def _from_preparation(prepared: WarehouseInventoryAdjustmentPreparationResult) -> WarehouseInventoryAdjustmentFlowResult:
        if prepared.status == "error":
            return WarehouseInventoryAdjustmentFlowResult(
                status="error",
                message=prepared.message,
                pending=[],
                inventory_code=prepared.inventory_code,
                prepared_count=prepared.prepared_count,
            )
        if prepared.status == "no_differences":
            return WarehouseInventoryAdjustmentFlowResult(
                status="no_differences",
                message=prepared.message,
                pending=[],
                inventory_code=prepared.inventory_code,
                prepared_count=prepared.prepared_count,
            )
        return WarehouseInventoryAdjustmentFlowResult(
            status="ready",
            message=prepared.message,
            pending=list(prepared.pending),
            inventory_code=prepared.inventory_code,
            prepared_count=prepared.prepared_count,
        )

    @staticmethod
    def _normalize_row(row: WarehouseInventoryAdjustmentRowInput | dict[str, Any]) -> WarehouseInventoryAdjustmentRowInput:
        if isinstance(row, WarehouseInventoryAdjustmentRowInput):
            return row
        return WarehouseInventoryAdjustmentRowInput(
            articulo_id=str(row.get("articulo_id", "") or ""),
            articulo_lote=str(row.get("articulo_lote", "") or ""),
            articulo_caducidad_iso=str(row.get("articulo_caducidad_iso", "") or ""),
            conteo_text=str(row.get("conteo_text", "") or ""),
            teorico_text=str(row.get("teorico_text", "") or ""),
            peso=float(row.get("peso", 0.0) or 0.0),
        )
