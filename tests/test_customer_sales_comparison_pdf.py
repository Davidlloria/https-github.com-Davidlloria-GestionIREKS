from types import SimpleNamespace

from pypdf import PdfReader

from app.services.report_export_service import ReportExportService
from app.ui.widgets.customers_page import CustomersPage


def _row(code: str, name: str, base: float) -> SimpleNamespace:
    return SimpleNamespace(
        codigo=code,
        nombre=name,
        unidades_prev=base,
        kg_prev=base * 2,
        euros_prev=base * 3,
        unidades_curr=base + 1,
        kg_curr=base * 2 + 1,
        euros_curr=base * 3 + 1,
        delta_unidades=1,
        delta_kg=1,
        delta_euros=1,
    )


def test_customer_sales_comparison_pdf_filename_uses_years_and_customer() -> None:
    assert (
        CustomersPage._sales_comparison_pdf_filename(2026, "Cliente Uno")
        == "Comparativa - 2025 vs 2026 - Cliente Uno.pdf"
    )


def test_export_customer_sales_comparison_pdf_contains_all_rows_and_totals(tmp_path) -> None:
    output = tmp_path / "Comparativa - 2025 vs 2026 - Cliente Uno.pdf"
    rows = [_row("ART-1", "Producto uno", 10), _row("ART-2", "Producto dos", 20)]

    result = ReportExportService().export_customer_sales_comparison_pdf(
        output,
        customer_name="Cliente Uno",
        year=2026,
        rows=rows,
    )

    assert result == output
    assert output.read_bytes().startswith(b"%PDF")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(output).pages)
    assert "Comparativa de ventas" in text
    assert "Cliente Uno" in text
    assert "2025 vs 2026" in text
    assert "Generado" in text
    assert "ART-1" in text
    assert "ART-2" in text
    assert "TOTALES" in text


def test_export_customer_sales_comparison_pdf_repeats_headers_on_multiple_pages(tmp_path) -> None:
    output = tmp_path / "comparativa-larga.pdf"
    rows = [_row(f"ART-{index:03d}", f"Producto número {index}", float(index)) for index in range(90)]

    ReportExportService().export_customer_sales_comparison_pdf(
        output,
        customer_name="Cliente Largo",
        year=2026,
        rows=rows,
    )

    pages = PdfReader(output).pages
    assert len(pages) > 1
    for page in pages:
        text = page.extract_text() or ""
        assert "Referencia" in text
        assert "Descripción" in text
