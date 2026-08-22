from __future__ import annotations

from app.services.report_export_service import ReportExportService


def test_customer_query_pdf_formats_weight_and_euros_in_spanish() -> None:
    service = ReportExportService()

    assert service._format_pdf_value("Kg", 18456) == "18.456,00 kg"
    assert service._format_pdf_value("€", 85585.45) == "85.585,45 €"


def test_customer_query_pdf_keeps_kg_and_euro_columns_at_the_same_width() -> None:
    widths = [40.0, 220.0, 70.0, 55.0]

    ReportExportService._match_pdf_measure_columns(["Cod.", "Nombre comercial", "Kg", "€"], widths)

    assert widths == [40.0, 220.0, 70.0, 70.0]
