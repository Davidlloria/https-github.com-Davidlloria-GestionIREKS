from __future__ import annotations

from pathlib import Path

from app.services.order_service import OrderItemsImportResult
from app.services.orders_items_import_ui_service import OrdersItemsImportUiService


class _FakeOrderService:
    def __init__(self, result: OrderItemsImportResult | None = None) -> None:
        self.result = result or OrderItemsImportResult(imported=4, errors=[])
        self.calls: list[Path] = []

    def import_order_items_file(self, source: Path) -> OrderItemsImportResult:
        self.calls.append(source)
        return self.result


def test_import_order_items_success(tmp_path: Path) -> None:
    source = tmp_path / "items.xlsx"
    source.write_text("x", encoding="utf-8")
    fake = _FakeOrderService(OrderItemsImportResult(imported=7, errors=[]))
    service = OrdersItemsImportUiService(order_service=fake)  # type: ignore[arg-type]

    outcome = service.import_order_items_file(source)

    assert outcome.ok is True
    assert outcome.imported == 7
    assert outcome.errors_count == 0
    assert "Items importados: 7" in outcome.message
    assert fake.calls == [source]


def test_import_order_items_with_errors_builds_preview(tmp_path: Path) -> None:
    source = tmp_path / "items.csv"
    source.write_text("x", encoding="utf-8")
    fake = _FakeOrderService(OrderItemsImportResult(imported=2, errors=["e1", "e2"]))
    service = OrdersItemsImportUiService(order_service=fake)  # type: ignore[arg-type]

    outcome = service.import_order_items_file(source)

    assert outcome.ok is False
    assert outcome.imported == 2
    assert outcome.errors_count == 2
    assert "Errores: 2" in outcome.message
    assert "e1" in outcome.message


def test_import_order_items_validates_file(tmp_path: Path) -> None:
    fake = _FakeOrderService()
    service = OrdersItemsImportUiService(order_service=fake)  # type: ignore[arg-type]

    txt = tmp_path / "items.txt"
    txt.write_text("x", encoding="utf-8")
    try:
        service.import_order_items_file(txt)
    except ValueError as exc:
        assert ".xlsx" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for invalid extension")

    try:
        service.import_order_items_file(tmp_path / "missing.xlsx")
    except ValueError as exc:
        assert "no existe" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for missing file")
