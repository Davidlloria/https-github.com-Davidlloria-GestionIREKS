from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.customer_ai_summary_service import (
    CustomerAISnapshot,
    CustomerAISummaryResult,
    CustomerAISummarySections,
)
from app.ui.widgets.customer_ai_summary_dialog import CustomerAISummaryDialog


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _result() -> CustomerAISummaryResult:
    snapshot = CustomerAISnapshot(
        customer_id="customer-1",
        customer_name="Panadería Ejemplo",
        customer_type="indirecto",
        activity="PANADERIA",
        active=True,
        year=2026,
        previous_year=2025,
        month_from=1,
        month_to=7,
        period_label="enero–julio 2026 frente a enero–julio 2025",
        comparison_available=True,
        comparison_note="",
        kg_current=80.0,
        kg_previous=130.0,
        euros_current=380.0,
        delta_kg=-50.0,
        delta_kg_pct=-38.46,
        latest_activity="2026-07-17",
    )
    sections = CustomerAISummarySections(
        situation="Cliente activo.",
        sales="El volumen desciende un 38,5%.",
        products=("Revisar Producto A.",),
        opportunities=("Contactar al cliente.",),
        conclusion="Priorizar el seguimiento.",
    )
    return CustomerAISummaryResult(
        True,
        "texto normalizado",
        "Resumen redactado con IA local.",
        True,
        snapshot,
        sections,
    )


def test_customer_ai_summary_dialog_shows_loading_and_structured_result() -> None:
    _application()
    dialog = CustomerAISummaryDialog(customer_name="Panadería Ejemplo")

    assert dialog.objectName() == "customerAISummaryDialog"
    assert dialog.windowTitle() == "Resumen IA · Panadería Ejemplo"
    assert dialog.summary_text.isReadOnly()
    assert dialog.progress.maximum() == 0
    assert dialog.retry_button.isEnabled() is False
    assert dialog.pdf_button.isEnabled() is False

    dialog.set_result(_result())

    assert dialog.progress.isHidden()
    assert dialog.retry_button.isEnabled() is True
    assert dialog.pdf_button.isEnabled() is True
    assert dialog.period_label.text() == "Enero–julio 2026 frente a enero–julio 2025"
    assert dialog.kg_value.text() == "80,00 kg"
    assert dialog.variation_value.text() == "-38.5%"
    assert dialog.revenue_value.text() == "380,00 €"
    plain_text = dialog.summary_text.toPlainText()
    assert "Situación" in plain_text
    assert "Contactar al cliente" in plain_text
    assert "**" not in plain_text

    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()


def test_customer_ai_summary_dialog_exports_pdf(monkeypatch, tmp_path: Path) -> None:
    class ExportServiceDouble:
        def __init__(self) -> None:
            self.call = None

        def default_path(self, title: str, suffix: str, *, folder: str) -> Path:
            assert title == "Resumen IA Panadería Ejemplo"
            assert suffix == "pdf"
            assert folder == "resumenes_ia_clientes"
            return tmp_path / "predeterminado.pdf"

        def export_customer_ai_summary_pdf(self, path: str, *, customer_name: str, result) -> Path:
            self.call = (path, customer_name, result)
            return Path(path)

    _application()
    export_service = ExportServiceDouble()
    output = tmp_path / "resumen.pdf"
    messages = []
    monkeypatch.setattr(
        "app.ui.widgets.customer_ai_summary_dialog.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(output), ""),
    )
    monkeypatch.setattr(
        "app.ui.widgets.customer_ai_summary_dialog.QMessageBox.information",
        lambda *args: messages.append(args),
    )
    dialog = CustomerAISummaryDialog(
        customer_name="Panadería Ejemplo",
        report_export_service=export_service,
    )
    result = _result()
    dialog.set_result(result)

    dialog.pdf_button.click()

    assert export_service.call == (str(output), "Panadería Ejemplo", result)
    assert messages
    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()


def test_customer_ai_summary_dialog_emits_retry() -> None:
    _application()
    dialog = CustomerAISummaryDialog(customer_name="Panadería Ejemplo")
    calls: list[bool] = []
    dialog.retry_requested.connect(lambda: calls.append(True))
    dialog.set_result(_result())

    dialog.retry_button.click()

    assert calls == [True]
    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()


def test_customer_ai_summary_dialog_marks_annual_reference_as_not_comparable() -> None:
    _application()
    dialog = CustomerAISummaryDialog(customer_name="Panadería Ejemplo")
    result = _result()
    snapshot = replace(
        result.snapshot,
        period_label="enero–agosto 2026 · referencia anual 2025 no comparable",
        comparison_available=False,
        comparison_note="2025 solo dispone de un acumulado anual.",
        kg_previous=30307.0,
        delta_kg=None,
        delta_kg_pct=None,
    )

    dialog.set_result(replace(result, snapshot=snapshot))

    assert dialog.variation_value.text() == "No comparable"
    assert "referencia anual 2025 no comparable" in dialog.period_label.text()
    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()
