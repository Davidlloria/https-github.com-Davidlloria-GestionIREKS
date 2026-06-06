from __future__ import annotations

from datetime import date

from app.services.warehouse_inventory_adjustment_preparation_service import (
    WarehouseInventoryAdjustmentPreparationService,
)


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


def test_prepare_adjustments_returns_no_differences_for_equal_values() -> None:
    service = WarehouseInventoryAdjustmentPreparationService()

    result = service.prepare_adjustments([_row(conteo_text="8", teorico_text="8")], almacen_id="ALM-1", today=date(2026, 6, 4))

    assert result.status == "no_differences"
    assert result.message == "No hay diferencias para ajustar."
    assert result.pending == []
    assert result.inventory_code == "INV-20260604"


def test_prepare_adjustments_returns_ready_for_one_valid_row() -> None:
    service = WarehouseInventoryAdjustmentPreparationService()

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


def test_prepare_adjustments_skips_empty_conteo() -> None:
    service = WarehouseInventoryAdjustmentPreparationService()

    result = service.prepare_adjustments([_row(conteo_text="")], almacen_id="ALM-1", today=date(2026, 6, 4))

    assert result.status == "no_differences"
    assert result.pending == []


def test_prepare_adjustments_skips_invalid_conteo() -> None:
    service = WarehouseInventoryAdjustmentPreparationService()

    result = service.prepare_adjustments([_row(conteo_text="abc")], almacen_id="ALM-1", today=date(2026, 6, 4))

    assert result.status == "no_differences"
    assert result.pending == []


def test_prepare_adjustments_skips_almost_equal_differences() -> None:
    service = WarehouseInventoryAdjustmentPreparationService()

    result = service.prepare_adjustments(
        [_row(conteo_text="8.00001", teorico_text="8.00000")],
        almacen_id="ALM-1",
        today=date(2026, 6, 4),
    )

    assert result.status == "no_differences"
    assert result.pending == []


def test_prepare_adjustments_allows_missing_caducidad() -> None:
    service = WarehouseInventoryAdjustmentPreparationService()

    result = service.prepare_adjustments(
        [_row(articulo_caducidad_iso="", conteo_text="12", teorico_text="8")],
        almacen_id="ALM-1",
        today=date(2026, 6, 4),
    )

    assert result.status == "ready"
    assert result.pending[0]["articulo_caducidad"] is None


def test_prepare_adjustments_returns_error_for_missing_almacen_id() -> None:
    service = WarehouseInventoryAdjustmentPreparationService()

    result = service.prepare_adjustments([_row()], almacen_id="   ", today=date(2026, 6, 4))

    assert result.status == "error"
    assert result.message == "Indica almacen_id."
    assert result.pending == []

