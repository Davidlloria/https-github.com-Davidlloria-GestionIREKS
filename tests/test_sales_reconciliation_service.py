import json

from app.services.sales_reconciliation_service import SalesReconciliationService


def test_read_ireks_json_accepts_utf16_bom(tmp_path) -> None:
    path = tmp_path / "ireks.json"
    rows = [{"venta_Anio": 2025, "venta_Mes": "Enero", "Codigo": "123"}]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-16")

    data = SalesReconciliationService()._read_json(path)

    assert data == rows


def test_import_ireks_json_returns_result_for_invalid_json(tmp_path) -> None:
    path = tmp_path / "ireks.json"
    path.write_text("{", encoding="utf-8")

    result = SalesReconciliationService().import_ireks_json(path)

    assert not result.ok
    assert "JSON valido" in result.message


def test_total_rows_are_skipped() -> None:
    service = SalesReconciliationService()

    assert service._is_total_row(" TOTAL ")
