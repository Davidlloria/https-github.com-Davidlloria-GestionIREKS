from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

from app.services.order_edit_flow_service import OrderEditFlowService


class _FakeOrderQueryService:
    def __init__(self, *, result: tuple[Any, dict[str, float]] | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[str] = []

    def get_order_edit_payload(self, pedido_id: str) -> tuple[Any, dict[str, float]]:
        self.calls.append(pedido_id)
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise ValueError("Pedido no encontrado.")
        return self.result


class _FakeOrderService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def update_order(
        self,
        *,
        pedido_id: str,
        pedido_fecha: date,
        pedido_numero: str,
        lines: list[Any],
        submit_mode: str,
    ) -> None:
        self.calls.append(
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


def test_build_edit_context_returns_ready_result() -> None:
    pedido = SimpleNamespace(almacen_id="alm-1", pedido_fecha=date(2026, 6, 1), pedido_numero="P-10")
    fake_query = _FakeOrderQueryService(result=(pedido, {"a": 2.5, "b": 1.0}))
    service = OrderEditFlowService(order_query_service=fake_query, order_service=_FakeOrderService())

    result = service.build_edit_context("ped-1")

    assert result.status == "ready"
    assert result.pedido_id == "ped-1"
    assert result.pedido == pedido
    assert result.qty_by_articulo == {"a": 2.5, "b": 1.0}
    assert fake_query.calls == ["ped-1"]


def test_build_edit_context_returns_not_found_for_missing_order() -> None:
    fake_query = _FakeOrderQueryService(error=ValueError("Pedido no encontrado."))
    service = OrderEditFlowService(order_query_service=fake_query, order_service=_FakeOrderService())

    result = service.build_edit_context("ped-1")

    assert result.status == "not_found"
    assert result.message == "Pedido no encontrado."
    assert result.pedido_id == "ped-1"


def test_build_edit_context_returns_error_for_unexpected_failure() -> None:
    fake_query = _FakeOrderQueryService(error=RuntimeError("fallo query"))
    service = OrderEditFlowService(order_query_service=fake_query, order_service=_FakeOrderService())

    result = service.build_edit_context("ped-1")

    assert result.status == "error"
    assert result.message == "fallo query"


def test_submit_edit_returns_empty_lines_without_saving() -> None:
    fake_order = _FakeOrderService()
    service = OrderEditFlowService(order_query_service=_FakeOrderQueryService(), order_service=fake_order)

    result = service.submit_edit("ped-1", date(2026, 6, 1), "P-10", [], "consignar")

    assert result.status == "empty_lines"
    assert fake_order.calls == []


def test_submit_edit_returns_success_and_calls_order_service() -> None:
    fake_order = _FakeOrderService()
    service = OrderEditFlowService(order_query_service=_FakeOrderQueryService(), order_service=fake_order)
    lines = [SimpleNamespace(articulo_id="art-1", uds=2.5), SimpleNamespace(articulo_id="art-2", uds=1)]

    result = service.submit_edit("ped-1", date(2026, 6, 1), "P-10", lines, "consignar")

    assert result.status == "success"
    assert len(fake_order.calls) == 1
    call = fake_order.calls[0]
    assert call["pedido_id"] == "ped-1"
    assert call["pedido_fecha"] == date(2026, 6, 1)
    assert call["pedido_numero"] == "P-10"
    assert call["submit_mode"] == "consignar"
    assert [(line.articulo_id, line.uds) for line in call["lines"]] == [("art-1", 2.5), ("art-2", 1.0)]


def test_submit_edit_returns_error_for_service_failure() -> None:
    fake_order = _FakeOrderService(error=RuntimeError("fallo update"))
    service = OrderEditFlowService(order_query_service=_FakeOrderQueryService(), order_service=fake_order)
    lines = [SimpleNamespace(articulo_id="art-1", uds=2.5)]

    result = service.submit_edit("ped-1", date(2026, 6, 1), "P-10", lines, "consignar")

    assert result.status == "error"
    assert result.message == "fallo update"


def test_submit_edit_returns_not_found_for_value_error() -> None:
    fake_order = _FakeOrderService(error=ValueError("Pedido no encontrado."))
    service = OrderEditFlowService(order_query_service=_FakeOrderQueryService(), order_service=fake_order)
    lines = [SimpleNamespace(articulo_id="art-1", uds=2.5)]

    result = service.submit_edit("ped-1", date(2026, 6, 1), "P-10", lines, "consignar")

    assert result.status == "not_found"
    assert result.message == "Pedido no encontrado."
