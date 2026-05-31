from __future__ import annotations

from pathlib import Path

from app.services.order_service import OrderJsonImportResult
from app.services.settings_orders_import_service import SettingsOrdersImportService


class _FakeSettingsImportService:
    def __init__(self, result: OrderJsonImportResult | None = None) -> None:
        self.result = result or OrderJsonImportResult(
            pedido_id="order-1",
            imported_items=3,
            skipped_unknown=["A-1", "B-2", "A-1"],
            skipped_invalid=1,
        )
        self.calls: list[tuple[Path, str]] = []

    def import_order_json(self, source: Path, almacen_id: str) -> OrderJsonImportResult:
        self.calls.append((source, almacen_id))
        return self.result


def test_import_orders_json_builds_summary_and_log(tmp_path: Path) -> None:
    source = tmp_path / "pedido.json"
    source.write_text("{}", encoding="utf-8")
    fake = _FakeSettingsImportService()
    service = SettingsOrdersImportService(settings_import_service=fake)

    outcome = service.import_orders_json(source, "alm-1")

    assert outcome.ok is True
    assert outcome.imported_items == 3
    assert outcome.skipped_unknown_count == 3
    assert outcome.skipped_invalid == 1
    assert "lineas=3" in outcome.log_message
    assert any("Lineas importadas: 3" in row for row in outcome.summary_lines)
    assert any("Codigos no encontrados" in row for row in outcome.summary_lines)
    assert fake.calls == [(source, "alm-1")]


def test_import_orders_json_validates_inputs(tmp_path: Path) -> None:
    fake = _FakeSettingsImportService()
    service = SettingsOrdersImportService(settings_import_service=fake)

    source_txt = tmp_path / "pedido.txt"
    source_txt.write_text("x", encoding="utf-8")

    try:
        service.import_orders_json(source_txt, "alm-1")
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

    source_ok = tmp_path / "pedido.json"
    source_ok.write_text("{}", encoding="utf-8")
    try:
        service.import_orders_json(source_ok, "")
    except ValueError as exc:
        assert "selecciona" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for empty almacen_id")

