from __future__ import annotations

from datetime import date
from typing import Any

from app.services.warehouse_inventory_adjustment_flow_service import (
    WarehouseInventoryAdjustmentFlowService,
)


class _FakeWarehouseInventoryService:
    def __init__(self, *, applied: int = 2, error: Exception | None = None) -> None:
        self.applied = applied
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def apply_adjustments(self, *, pending: list[dict[str, Any]], almacen_id: str, contador: str, aprobador: str) -> int:
        self.calls.append(
            {
                "pending": list(pending),
                "almacen_id": almacen_id,
                "contador": contador,
                "aprobador": aprobador,
            }
        )
        if self.error is not None:
            raise self.error
        return self.applied


def _row(
    *,
    articulo_id: str = "A1",
    articulo_lote: str = "L1",
    articulo_caducidad_iso: str = "2026-06-30",
    conteo_text: str = "10",
    teorico_text: str = "8",
    peso: float = 2.5,
) -> dict[str, object]:
    return {
        "articulo_id": articulo_id,
        "articulo_lote": articulo_lote,
        "articulo_caducidad_iso": articulo_caducidad_iso,
        "conteo_text": conteo_text,
        "teorico_text": teorico_text,
        "peso": peso,
    }


def test_build_row_inputs_normalizes_dict_rows() -> None:
    service = WarehouseInventoryAdjustmentFlowService()

    rows = service.build_row_inputs([_row()])

    assert len(rows) == 1
    assert rows[0].articulo_id == "A1"
    assert rows[0].articulo_lote == "L1"
    assert rows[0].conteo_text == "10"


def test_prepare_adjustments_returns_no_differences_for_equal_values() -> None:
    service = WarehouseInventoryAdjustmentFlowService()

    result = service.prepare_adjustments([_row(conteo_text="8", teorico_text="8")], almacen_id="ALM-1", today=date(2026, 6, 4))

    assert result.status == "no_differences"
    assert result.message == "No hay diferencias para ajustar."
    assert result.pending == []
    assert result.inventory_code == "INV-20260604"


def test_prepare_adjustments_returns_ready_for_one_valid_row() -> None:
    service = WarehouseInventoryAdjustmentFlowService()

    result = service.prepare_adjustments([_row()], almacen_id="ALM-1", today=date(2026, 6, 4))

    assert result.status == "ready"
    assert result.prepared_count == 1
    assert result.inventory_code == "INV-20260604"
    assert result.message == "Ajustes preparados: 1\nRevisa y pulsa 'Aprobar y aplicar'."
    assert len(result.pending) == 1
    pending = result.pending[0]
    mov = pending["mov"]
    assert mov.pedido_numero == "INV-20260604"
    assert mov.pedido_albaran_numero == "INV-AJUSTE"
    assert mov.almacen_id == "ALM-1"
    assert mov.articulo_id == "A1"
    assert pending["diferencia_uds"] == 2.0
    assert pending["kg_ajuste"] == 5.0


def test_validate_application_rejects_missing_approval_fields() -> None:
    service = WarehouseInventoryAdjustmentFlowService()
    prepared = service.prepare_adjustments([_row()], almacen_id="ALM-1", today=date(2026, 6, 4))

    result = service.validate_application(prepared, contador="", aprobador="Oper")

    assert result.status == "invalid_approval"
    assert "Contador y Aprobador" in result.message


def test_apply_adjustments_uses_fake_inventory_service() -> None:
    fake_inventory = _FakeWarehouseInventoryService(applied=3)
    service = WarehouseInventoryAdjustmentFlowService(inventory_service=fake_inventory)
    prepared = service.prepare_adjustments([_row()], almacen_id="ALM-1", today=date(2026, 6, 4))
    validation = service.validate_application(prepared, contador="Cont-1", aprobador="Aprob-1")

    result = service.apply_adjustments(validation, almacen_id="ALM-1", contador=validation.contador, aprobador=validation.aprobador)

    assert result.status == "success"
    assert result.message == "Ajustes aplicados: 3"
    assert result.applied_count == 3
    assert len(fake_inventory.calls) == 1
    assert fake_inventory.calls[0]["contador"] == "Cont-1"
    assert fake_inventory.calls[0]["aprobador"] == "Aprob-1"


def test_apply_adjustments_returns_no_differences_when_not_prepared() -> None:
    service = WarehouseInventoryAdjustmentFlowService()

    result = service.apply_adjustments(
        service.validate_application(
            service.prepare_adjustments([_row(conteo_text="8", teorico_text="8")], almacen_id="ALM-1", today=date(2026, 6, 4)),
            contador="Cont-1",
            aprobador="Aprob-1",
        ),
        almacen_id="ALM-1",
        contador="Cont-1",
        aprobador="Aprob-1",
    )

    assert result.status == "no_differences"
