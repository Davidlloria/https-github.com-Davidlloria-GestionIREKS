from __future__ import annotations

from pathlib import Path

from app.services.settings_sales_preview_service import SettingsSalesPreviewService


class _FakeSalesService:
    def parse_igsa_pdf_files(self, paths: list[Path]):  # noqa: ANN201
        return ([{"source_file": p.name} for p in paths], ["warn-pdf"])

    def parse_igsa_workbook_by_sheets(self, path: Path):  # noqa: ANN201
        return ([{"sheet": path.name}], ["warn-parse"])

    def build_igsa_workbook_preview(self, lines: list[object], cliente_id: str):  # noqa: ANN201
        _ = cliente_id
        return ([{"preview": len(lines)}], ["warn-preview"])


class _FakeSettingsImportService:
    def __init__(self, cliente_id: str = "igsa-1") -> None:
        self.cliente_id = cliente_id

    def resolve_igsa_cliente_id(self) -> str:
        return self.cliente_id


def test_pdf_and_workbook_preview_happy_path(tmp_path: Path) -> None:
    pdf1 = tmp_path / "a.pdf"
    pdf2 = tmp_path / "b.pdf"
    pdf1.write_text("x", encoding="utf-8")
    pdf2.write_text("y", encoding="utf-8")
    book = tmp_path / "book.xlsx"
    book.write_text("z", encoding="utf-8")

    service = SettingsSalesPreviewService(
        sales_service=_FakeSalesService(),  # type: ignore[arg-type]
        settings_import_service=_FakeSettingsImportService(),
    )

    pdf = service.preview_igsa_pdf_files([pdf1, pdf2])
    assert len(pdf.lines) == 2
    assert pdf.errors == ["warn-pdf"]

    workbook = service.preview_igsa_workbook(book)
    assert len(workbook.raw_lines) == 1
    assert len(workbook.preview_rows) == 1
    assert workbook.errors == ["warn-parse", "warn-preview"]


def test_preview_validations_raise_value_error(tmp_path: Path) -> None:
    service = SettingsSalesPreviewService(
        sales_service=_FakeSalesService(),  # type: ignore[arg-type]
        settings_import_service=_FakeSettingsImportService(cliente_id=""),
    )

    try:
        service.preview_igsa_pdf_files([])
    except ValueError as exc:
        assert "al menos" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for empty file list")

    txt = tmp_path / "a.txt"
    txt.write_text("x", encoding="utf-8")
    try:
        service.preview_igsa_pdf_files([txt])
    except ValueError as exc:
        assert ".pdf" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for non-pdf file")

    book = tmp_path / "book.xlsx"
    book.write_text("x", encoding="utf-8")
    try:
        service.preview_igsa_workbook(book)
    except ValueError as exc:
        assert "cliente/distribuidor" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError when IGSA client is unresolved")
