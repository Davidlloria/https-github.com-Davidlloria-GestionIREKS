import json
from pathlib import Path

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


class _FakePdfFlowService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def parse_igsa_pdf_files(self, file_paths: list[Path]) -> tuple[list[object], list[str]]:
        self.calls.append(("parse_igsa_pdf_files", (list(file_paths),), {}))
        return ["parsed"], ["parse-error"]

    def import_igsa_pdf_lines(
        self,
        lines: list[object],
        cliente_id: str = "",
        *,
        sync_warehouse_callback=None,
    ):
        self.calls.append(
            (
                "import_igsa_pdf_lines",
                (list(lines),),
                {"cliente_id": cliente_id, "sync_warehouse_callback": sync_warehouse_callback},
            )
        )
        return type("Result", (), {"ok": True, "message": "ok", "imported": 2, "incidencias": 1})()


def test_pdf_wrappers_delegate_to_flow_service() -> None:
    service = SalesReconciliationService()
    fake = _FakePdfFlowService()
    service._igsa_pdf_flow_service = fake  # type: ignore[assignment]

    parsed = service.parse_igsa_pdf_files([Path("a.pdf")])
    result = service.import_igsa_pdf_lines([object()], cliente_id="cliente-1")

    assert parsed == (["parsed"], ["parse-error"])
    assert result.ok is True
    assert fake.calls[0][0] == "parse_igsa_pdf_files"
    assert fake.calls[1][0] == "import_igsa_pdf_lines"
    assert fake.calls[1][2]["cliente_id"] == "cliente-1"
    assert callable(fake.calls[1][2]["sync_warehouse_callback"])
