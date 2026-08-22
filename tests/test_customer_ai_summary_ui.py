from __future__ import annotations

import os

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

    dialog.set_result(_result())

    assert dialog.progress.isHidden()
    assert dialog.retry_button.isEnabled() is True
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
