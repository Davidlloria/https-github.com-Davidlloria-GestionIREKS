from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.order_document_import_service import OrderDocumentImportResult
from app.services.orders_documents_import_ui_service import OrdersDocumentsImportUiService


class _FakeImportService:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[Path, list[dict[str, str]], dict[str, list[str]]]] = []

    def map_rows(self, file_path: Path, schema: list[dict[str, str]], aliases: dict[str, list[str]]) -> list[dict[str, Any]]:
        self.calls.append((file_path, schema, aliases))
        return list(self.rows)


class _FakeOrderDocumentImportService:
    def __init__(self) -> None:
        self.albaran_result = OrderDocumentImportResult(imported=3, errors=[], already_imported=False, message="")
        self.factura_result = OrderDocumentImportResult(imported=2, errors=[], already_imported=False, message="")
        self.albaran_calls: list[tuple[str, dict[str, str], list[dict[str, Any]]]] = []
        self.factura_calls: list[tuple[str, dict[str, str], list[dict[str, Any]]]] = []

    def enrich_factura_rows_from_tarifa(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [dict(row, enriched=True) for row in rows]

    def import_albaran(
        self,
        pedido_id: str,
        header: dict[str, str],
        rows: list[dict[str, Any]],
    ) -> OrderDocumentImportResult:
        self.albaran_calls.append((pedido_id, header, rows))
        return self.albaran_result

    def import_factura(
        self,
        pedido_id: str,
        header: dict[str, str],
        rows: list[dict[str, Any]],
    ) -> OrderDocumentImportResult:
        self.factura_calls.append((pedido_id, header, rows))
        return self.factura_result


def test_prepare_albaran_preview_uses_parser_for_pdf(tmp_path: Path) -> None:
    source = tmp_path / "alb.pdf"
    source.write_text("x", encoding="utf-8")
    fake_import = _FakeImportService()
    fake_docs = _FakeOrderDocumentImportService()
    service = OrdersDocumentsImportUiService(
        import_service=fake_import,  # type: ignore[arg-type]
        order_document_import_service=fake_docs,  # type: ignore[arg-type]
    )

    expected_header = {"albaran_numero": "A-1"}
    expected_rows = [{"articulo_codigo": "X"}]
    preview = service.prepare_albaran_preview(source, parse_pdf=lambda _p: (expected_header, expected_rows))

    assert preview.header == expected_header
    assert preview.rows == expected_rows
    assert fake_import.calls == []


def test_prepare_factura_preview_non_pdf_maps_and_enriches(tmp_path: Path) -> None:
    source = tmp_path / "fac.xlsx"
    source.write_text("x", encoding="utf-8")
    mapped = [{"factura_numero": "F-1", "articulo_codigo": "X"}]
    fake_import = _FakeImportService(rows=mapped)
    fake_docs = _FakeOrderDocumentImportService()
    service = OrdersDocumentsImportUiService(
        import_service=fake_import,  # type: ignore[arg-type]
        order_document_import_service=fake_docs,  # type: ignore[arg-type]
    )

    preview = service.prepare_factura_preview(source, parse_pdf=lambda _p: ({}, []))

    assert preview.header["factura_numero"] == "F-1"
    assert preview.rows[0]["enriched"] is True
    assert len(fake_import.calls) == 1


def test_prepare_preview_validates_source_and_rows(tmp_path: Path) -> None:
    fake_import = _FakeImportService(rows=[])
    fake_docs = _FakeOrderDocumentImportService()
    service = OrdersDocumentsImportUiService(
        import_service=fake_import,  # type: ignore[arg-type]
        order_document_import_service=fake_docs,  # type: ignore[arg-type]
    )

    txt = tmp_path / "file.txt"
    txt.write_text("x", encoding="utf-8")
    try:
        service.prepare_albaran_preview(txt, parse_pdf=lambda _p: ({}, []))
    except ValueError as exc:
        assert ".pdf" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for invalid extension")

    csv = tmp_path / "file.csv"
    csv.write_text("x", encoding="utf-8")
    try:
        service.prepare_albaran_preview(csv, parse_pdf=lambda _p: ({}, []))
    except ValueError as exc:
        assert "lineas" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for empty mapped rows")


def test_import_outcomes_cover_success_errors_and_already_imported() -> None:
    fake_import = _FakeImportService(rows=[])
    fake_docs = _FakeOrderDocumentImportService()
    service = OrdersDocumentsImportUiService(
        import_service=fake_import,  # type: ignore[arg-type]
        order_document_import_service=fake_docs,  # type: ignore[arg-type]
    )

    success = service.import_albaran(pedido_id="p1", header={}, rows=[{}])
    assert success.ok is True
    assert "Lineas de albaran importadas: 3" in success.message

    fake_docs.albaran_result = OrderDocumentImportResult(
        imported=1,
        errors=["e1", "e2"],
        already_imported=False,
        message="",
    )
    warning = service.import_albaran(pedido_id="p1", header={}, rows=[{}])
    assert warning.ok is False
    assert "Errores: 2" in warning.message

    fake_docs.factura_result = OrderDocumentImportResult(
        imported=0,
        errors=[],
        already_imported=True,
        message="Ya existe",
    )
    already = service.import_factura(pedido_id="p1", header={}, rows=[{}])
    assert already.ok is True
    assert already.already_imported is True
    assert already.title == "Factura ya importada"
    assert already.message == "Ya existe"
