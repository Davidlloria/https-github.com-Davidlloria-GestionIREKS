from __future__ import annotations

from types import SimpleNamespace

from pypdf import PdfReader

from app.services.report_export_service import ReportExportService


def _summary_result():
    snapshot = SimpleNamespace(
        period_label="enero-agosto 2026 - históricos anuales 2025 y 2024",
        comparison_available=False,
        delta_kg_pct=None,
        kg_current=18456.0,
        euros_current=85585.45,
        latest_activity="2026-07-17",
    )
    sections = SimpleNamespace(
        situation="Cliente activo con cuatro contactos registrados.",
        sales="El periodo actual suma 18.456,00 kg; 2025 y 2024 son acumulados anuales.",
        products=("REX RUSTICO: 10.425,00 kg.", "MUFFIN PLUS: 6.000,00 kg."),
        opportunities=("Mantener el seguimiento comercial.",),
        conclusion="La referencia anual no permite calcular una variacion comparable.",
    )
    return SimpleNamespace(
        snapshot=snapshot,
        sections=sections,
        message="Resumen redactado con IA local a partir de datos calculados por GestionIREKS.",
    )


def test_export_customer_ai_summary_pdf_contains_metrics_and_sections(tmp_path) -> None:
    output = tmp_path / "resumen-cliente.pdf"

    result = ReportExportService().export_customer_ai_summary_pdf(
        output,
        customer_name="Panificadora Ejemplo",
        result=_summary_result(),
    )

    assert result == output
    assert result.exists()
    reader = PdfReader(str(result))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Resumen comercial - Panificadora Ejemplo" in text
    assert "18.456,00 kg" in text
    assert "No comparable" in text
    assert "Situación" in text
    assert "REX RUSTICO" in text
    assert "Conclusión" in text
    assert "Página 1" in text
    assert "Resumen redactado con IA local a partir de datos calculados por GestionIREKS." not in text


def test_export_customer_ai_summary_pdf_adds_pdf_suffix(tmp_path) -> None:
    output = tmp_path / "resumen-cliente"

    result = ReportExportService().export_customer_ai_summary_pdf(
        output,
        customer_name="Cliente",
        result=_summary_result(),
    )

    assert result == output.with_suffix(".pdf")
    assert result.exists()
