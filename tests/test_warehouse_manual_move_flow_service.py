from __future__ import annotations

from datetime import date

from app.models import AlmacenMovimiento
from app.services.warehouse_manual_move_flow_service import WarehouseManualMoveFlowService


class FakeWarehouseMovementService:
    def __init__(self, *, stock: float = 0.0, saved_move: AlmacenMovimiento | None = None, save_error: Exception | None = None) -> None:
        self.stock = stock
        self.saved_move = saved_move or AlmacenMovimiento(
            id=999,
            almacen_id="ALM-1",
            articulo_id="ART-1",
            pedido_numero="MANUAL-20240604",
            pedido_albaran_numero="MANUAL-IN|MOT:Alta|USR:Oper",
            cantidad=3.0,
            articulo_lote="LOT-1",
            articulo_caducidad=None,
            fecha_pedido=date(2026, 6, 4),
            albaran_item_id="item-1",
        )
        self.save_error = save_error
        self.current_stock_calls: list[dict[str, object]] = []
        self.save_calls: list[dict[str, object]] = []

    def current_stock_for(self, *, almacen_id: str, articulo_id: str, lote: str, caducidad: date | None) -> float:
        self.current_stock_calls.append(
            {
                "almacen_id": almacen_id,
                "articulo_id": articulo_id,
                "lote": lote,
                "caducidad": caducidad,
            }
        )
        return self.stock

    def save_manual_move(
        self,
        *,
        payload: dict[str, object],
        mode: str,
        almacen_id: str,
        existing: AlmacenMovimiento | None,
        fecha_pedido: date,
        caducidad: date | None,
        albaran: str,
    ) -> AlmacenMovimiento:
        self.save_calls.append(
            {
                "payload": dict(payload),
                "mode": mode,
                "almacen_id": almacen_id,
                "existing": existing,
                "fecha_pedido": fecha_pedido,
                "caducidad": caducidad,
                "albaran": albaran,
            }
        )
        if self.save_error is not None:
            raise self.save_error
        return self.saved_move


def _payload(
    *,
    articulo_id: str = "ART-1",
    cantidad: object = "3",
    fecha_pedido: str = "2026-06-04",
    articulo_caducidad: str = "",
    articulo_lote: str = "LOT-1",
    motivo: str = "Alta",
    usuario: str = "Oper",
    observacion: str = "Obs",
) -> dict[str, object]:
    return {
        "articulo_id": articulo_id,
        "cantidad": cantidad,
        "fecha_pedido": fecha_pedido,
        "articulo_caducidad": articulo_caducidad,
        "articulo_lote": articulo_lote,
        "motivo": motivo,
        "usuario": usuario,
        "observacion": observacion,
    }


def test_build_context_and_submit_for_inbound_move() -> None:
    fake = FakeWarehouseMovementService(stock=25.0)
    service = WarehouseManualMoveFlowService(movement_service=fake)

    context = service.build_manual_move_context(
        _payload(),
        mode="in",
        almacen_id="ALM-1",
        existing=None,
    )

    assert context.status == "ready"
    assert context.mode == "in"
    assert context.almacen_id == "ALM-1"
    assert context.quantity_signed == 3.0
    assert context.stock == 0.0
    assert context.albaran == "MANUAL-IN|MOT:Alta|USR:Oper|OBS:Obs"

    result = service.submit_manual_move(context)

    assert result.status == "success"
    assert result.move is fake.saved_move
    assert len(fake.current_stock_calls) == 0
    assert len(fake.save_calls) == 1
    assert fake.save_calls[0]["mode"] == "in"
    assert fake.save_calls[0]["almacen_id"] == "ALM-1"
    assert fake.save_calls[0]["existing"] is None


def test_build_context_and_submit_for_editing_move() -> None:
    existing = AlmacenMovimiento(
        id=12,
        almacen_id="ALM-1",
        articulo_id="ART-1",
        pedido_numero="MANUAL-20240604",
        pedido_albaran_numero="MANUAL-OUT|MOT:Salida|USR:Oper",
        cantidad=-2.0,
        articulo_lote="LOT-1",
        articulo_caducidad=None,
        fecha_pedido=date(2026, 6, 4),
        albaran_item_id="item-2",
    )
    fake = FakeWarehouseMovementService(stock=10.0)
    service = WarehouseManualMoveFlowService(movement_service=fake)

    context = service.build_manual_move_context(
        _payload(cantidad="2", motivo="Salida", usuario="Oper"),
        mode="out",
        almacen_id="ALM-1",
        existing=existing,
    )

    assert context.status == "ready"
    assert context.mode == "out"
    assert context.existing is existing
    assert context.quantity_signed == -2.0
    assert context.stock == 12.0

    result = service.submit_manual_move(context)

    assert result.status == "success"
    assert result.move is fake.saved_move
    assert len(fake.current_stock_calls) == 1
    assert fake.current_stock_calls[0]["articulo_id"] == "ART-1"
    assert fake.save_calls[0]["existing"] is existing


def test_invalid_article_and_quantity_are_rejected() -> None:
    fake = FakeWarehouseMovementService()
    service = WarehouseManualMoveFlowService(movement_service=fake)

    result_article = service.build_manual_move_context(
        _payload(articulo_id=""),
        mode="in",
        almacen_id="ALM-1",
        existing=None,
    )
    assert result_article.status == "invalid_payload"
    assert result_article.message == "Articulo_ID es obligatorio."

    result_qty = service.build_manual_move_context(
        _payload(cantidad="abc"),
        mode="in",
        almacen_id="ALM-1",
        existing=None,
    )
    assert result_qty.status == "invalid_payload"
    assert result_qty.message == "Cantidad no valida."


def test_insufficient_stock_is_reported_before_save() -> None:
    fake = FakeWarehouseMovementService(stock=1.0)
    service = WarehouseManualMoveFlowService(movement_service=fake)

    result = service.build_manual_move_context(
        _payload(cantidad="2", motivo="Salida", usuario="Oper"),
        mode="out",
        almacen_id="ALM-1",
        existing=None,
    )

    assert result.status == "insufficient_stock"
    assert "stock negativo" in result.message
    assert len(fake.current_stock_calls) == 1
    assert len(fake.save_calls) == 0


def test_submit_turns_service_error_into_structured_error() -> None:
    fake = FakeWarehouseMovementService(save_error=RuntimeError("boom"))
    service = WarehouseManualMoveFlowService(movement_service=fake)

    context = service.build_manual_move_context(
        _payload(),
        mode="in",
        almacen_id="ALM-1",
        existing=None,
    )
    result = service.submit_manual_move(context)

    assert result.status == "error"
    assert result.message == "boom"
    assert len(fake.save_calls) == 1
