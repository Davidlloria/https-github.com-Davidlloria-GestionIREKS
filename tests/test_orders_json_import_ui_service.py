from __future__ import annotations

from pathlib import Path

from app.services.order_service import OrderJsonImportResult
from app.services.orders_json_import_ui_service import OrdersJsonImportUiService


class _FakeOrderService:
    def __init__(self, result: OrderJsonImportResult | None = None) -> None:
        self.result = result or OrderJsonImportResult(
            pedido_id="ped-1",
            imported_items=5,
            skipped_unknown=["X-1", "Y-2", "X-1"],
            skipped_invalid=2,
        )
        self.calls: list[tuple[Path, str]] = []

    def import_order_json(self, source: Path, almacen_id: str) -> OrderJsonImportResult:
        self.calls.append((source, almacen_id))
        return self.result


def test_resolve_almacen_id_prefers_filter_and_falls_back_to_selected() -> None:
    service = OrdersJsonImportUiService(order_service=_FakeOrderService())  # type: ignore[arg-type]

    assert service.resolve_almacen_id("alm-filter", "alm-selected") == "alm-filter"
    assert service.resolve_almacen_id("", "alm-selected") == "alm-selected"

    try:
        service.resolve_almacen_id("", "")
    except ValueError as exc:
        assert "cliente/distribuidor" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for empty almacen_id")


def test_import_orders_json_builds_summary(tmp_path: Path) -> None:
    source = tmp_path / "pedido.json"
    source.write_text("{}", encoding="utf-8")
    fake = _FakeOrderService()
    service = OrdersJsonImportUiService(order_service=fake)  # type: ignore[arg-type]

    outcome = service.import_orders_json(source, "alm-1")

    assert outcome.ok is True
    assert outcome.pedido_id == "ped-1"
    assert outcome.imported_items == 5
    assert outcome.skipped_unknown_count == 3
    assert outcome.skipped_invalid == 2
    assert any("Lineas importadas: 5" in row for row in outcome.summary_lines)
    assert any("Codigos no encontrados" in row for row in outcome.summary_lines)
    assert fake.calls == [(source, "alm-1")]


def test_import_orders_json_validates_file(tmp_path: Path) -> None:
    fake = _FakeOrderService()
    service = OrdersJsonImportUiService(order_service=fake)  # type: ignore[arg-type]

    txt = tmp_path / "pedido.txt"
    txt.write_text("x", encoding="utf-8")
    try:
        service.import_orders_json(txt, "alm-1")
    except ValueError as exc:
        assert ".json" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for non-json input")

    try:
        service.import_orders_json(tmp_path / "missing.json", "alm-1")
    except ValueError as exc:
        assert "no existe" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for missing file")
