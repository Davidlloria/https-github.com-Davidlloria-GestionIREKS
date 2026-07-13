from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from app.ui.widgets.customer_queries_dialog import CustomerQueriesDialog
from app.ui.widgets.customers_page import CustomersPage


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_customer_queries_dialog_exposes_named_controls() -> None:
    _application()
    dialog = CustomerQueriesDialog()

    assert dialog.objectName() == "customerQueriesDialog"
    assert dialog.prompt.objectName() == "customerQueryPrompt"
    assert dialog.results_table.objectName() == "customerQueryResultsTable"
    assert dialog.run_button.objectName() == "customerQueryRunButton"
    assert dialog.close_button.objectName() == "customerQueriesCloseButton"


def test_customer_code_is_not_formatted_as_decimal() -> None:
    _application()
    dialog = CustomerQueriesDialog()

    assert dialog._table_item('Cod.', 35).text() == '35'
    assert dialog._table_item('Kg', 35).text() == '35,00'


def test_customers_top_ribbon_contains_queries_button(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()

    button = page.findChild(QPushButton, "customerQueriesButton")

    assert button is not None
    assert button.text() == "Consultas"
    assert not button.icon().isNull()
