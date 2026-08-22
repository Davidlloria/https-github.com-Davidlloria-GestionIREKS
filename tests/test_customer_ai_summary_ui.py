from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.widgets.customer_ai_summary_dialog import CustomerAISummaryDialog


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_customer_ai_summary_dialog_is_read_only() -> None:
    _application()
    dialog = CustomerAISummaryDialog(
        customer_name="Panadería Ejemplo",
        summary="Resumen comercial",
        status="Generado con IA local",
    )

    assert dialog.objectName() == "customerAISummaryDialog"
    assert dialog.windowTitle() == "Resumen IA · Panadería Ejemplo"
    assert dialog.summary_text.isReadOnly()
    assert dialog.summary_text.toPlainText() == "Resumen comercial"
    assert dialog.status_label.text() == "Generado con IA local"

    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()
