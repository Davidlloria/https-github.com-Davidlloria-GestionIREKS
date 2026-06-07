from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

from app.services.order_selected_flow_service import OrderSelectedFlowService


class _FakeOrderEditFlowService:
    def __init__(self, *, context: Any | None = None, submit_result: Any | None = None, error: Exception | None = None) -> None:
        self.context = context
        self.submit_result = submit_result
        self.error = error
        self.build_calls: list[str] = []
        self.submit_calls: list[dict[str, Any]] = []

    def build_edit_context(self, pedido_id: str) -> Any:
        self.build_calls.append(pedido_id)
        if self.error is not None:
            raise self.error
        return self.context

    def submit_edit(self, pedido_id: str, pedido_fecha: date, pedido_numero: str, lines: list[Any], submit_mode: str) -> Any:
        self.submit_calls.append(
            {
                "pedido_id": pedido_id,
                "pedido_fecha": pedido_fecha,
                "pedido_numero": pedido_numero,
                "lines": list(lines),
                "submit_mode": submit_mode,
            }
        )
        if self.error is not None:
            raise self.error
        return self.submit_result


class _FakeOrderService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def update_order_header(self, pedido_id: str, pedido_fecha: date, pedido_numero: str) -> None:
        self.calls.append(
            {
                "pedido_id": pedido_id,
                "pedido_fecha": pedido_fecha,
                "pedido_numero": pedido_numero,
            }
        )
        if self.error is not None:
            raise self.error


def test_build_edit_context_returns_ready_state_with_ui_flags() -> None:
    pedido = SimpleNamespace(almacen_id="alm-1")
    fake_edit = _FakeOrderEditFlowService(
        context=SimpleNamespace(status="ready", pedido_id="ped-1", pedido=pedido, qty_by_articulo={"art-1": 2.5})
    )
    service = OrderSelectedFlowService(order_edit_flow_service=fake_edit, order_service=_FakeOrderService())

    result = service.build_edit_context("ped-1", "E")

    assert result.status == "ready"
    assert result.pedido_id == "ped-1"
    assert result.pedido == pedido
    assert result.qty_by_articulo == {"art-1": 2.5}
    assert result.confirm_label == "Guardar"
    assert result.allow_pending is False
    assert fake_edit.build_calls == ["ped-1"]


def test_build_edit_context_marks_pending_orders_as_allow_pending() -> None:
    fake_edit = _FakeOrderEditFlowService(
        context=SimpleNamespace(status="ready", pedido_id="ped-1", pedido=None, qty_by_articulo={})
    )
    service = OrderSelectedFlowService(order_edit_flow_service=fake_edit, order_service=_FakeOrderService())

    result = service.build_edit_context("ped-1", "P")

    assert result.status == "ready"
    assert result.confirm_label == "Consignar"
    assert result.allow_pending is True


def test_build_edit_context_propagates_not_found() -> None:
    fake_edit = _FakeOrderEditFlowService(context=SimpleNamespace(status="not_found", message="Pedido no encontrado."))
    service = OrderSelectedFlowService(order_edit_flow_service=fake_edit, order_service=_FakeOrderService())

    result = service.build_edit_context("ped-1", "E")

    assert result.status == "not_found"
    assert result.message == "Pedido no encontrado."


def test_save_selected_order_header_calls_order_service() -> None:
    fake_order = _FakeOrderService()
    service = OrderSelectedFlowService(order_edit_flow_service=_FakeOrderEditFlowService(), order_service=fake_order)

    result = service.save_selected_order_header("ped-1", date(2026, 6, 1), "P-10")

    assert result.status == "success"
    assert fake_order.calls == [
        {
            "pedido_id": "ped-1",
            "pedido_fecha": date(2026, 6, 1),
            "pedido_numero": "P-10",
        }
    ]


def test_save_selected_order_header_returns_error_for_service_failure() -> None:
    fake_order = _FakeOrderService(error=RuntimeError("fallo header"))
    service = OrderSelectedFlowService(order_edit_flow_service=_FakeOrderEditFlowService(), order_service=fake_order)

    result = service.save_selected_order_header("ped-1", date(2026, 6, 1), "P-10")

    assert result.status == "error"
    assert result.message == "fallo header"


def test_submit_selected_order_edit_delegates_to_edit_flow() -> None:
    fake_edit = _FakeOrderEditFlowService(submit_result=SimpleNamespace(status="success", message="", pedido_id="ped-1"))
    service = OrderSelectedFlowService(order_edit_flow_service=fake_edit, order_service=_FakeOrderService())
    lines = [SimpleNamespace(articulo_id="art-1", uds=2.5)]

    result = service.submit_selected_order_edit("ped-1", date(2026, 6, 1), "P-10", lines, "consignar")

    assert result.status == "success"
    assert len(fake_edit.submit_calls) == 1
    call = fake_edit.submit_calls[0]
    assert call["pedido_id"] == "ped-1"
    assert call["pedido_fecha"] == date(2026, 6, 1)
    assert call["pedido_numero"] == "P-10"
    assert call["submit_mode"] == "consignar"
    assert [(line.articulo_id, line.uds) for line in call["lines"]] == [("art-1", 2.5)]


def test_submit_selected_order_edit_returns_not_found_without_id() -> None:
    fake_edit = _FakeOrderEditFlowService(submit_result=SimpleNamespace(status="success", message="", pedido_id=""))
    service = OrderSelectedFlowService(order_edit_flow_service=fake_edit, order_service=_FakeOrderService())

    result = service.submit_selected_order_edit("", date(2026, 6, 1), "P-10", [], "consignar")

    assert result.status == "not_found"
    assert fake_edit.submit_calls == []
