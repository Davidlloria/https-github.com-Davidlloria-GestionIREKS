from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCalendarWidget, QDateEdit, QPushButton

from app.ui.widgets.customer_queries_dialog import CustomerQueriesDialog
from app.ui.widgets.customers_page import CustomersPage

_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_customer_queries_dialog_exposes_named_controls() -> None:
    _application()
    dialog = CustomerQueriesDialog()

    assert dialog.objectName() == "customerQueriesDialog"
    assert dialog.prompt.objectName() == "customerQueryPrompt"
    assert dialog.results_table.objectName() == "customerQueryResultsTable"
    assert dialog.run_button.objectName() == "customerQueryRunButton"
    assert dialog.close_button.objectName() == "customerQueriesCloseButton"
    assert dialog.clear_button.objectName() == 'customerQueryClearButton'
    assert dialog.findChildren(QPushButton, 'customerQueryExampleButton') == []
    assert '#60A5FA' in dialog.run_button.styleSheet()
    image = dialog.run_button.icon().pixmap(16, 16).toImage()
    colors = {
        image.pixelColor(x, y).name()
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() > 0
    }
    assert colors == {'#ffffff'}
    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()


def test_customer_query_clear_button_resets_the_dialog() -> None:
    _application()
    dialog = CustomerQueriesDialog()
    dialog.prompt.setPlainText('consulta')
    dialog.interpretation_label.setText('interpretada')
    dialog.status_label.setText('resultado')
    dialog._render_rows(['Kg'], [[12.0]])

    dialog._clear_query()

    assert dialog.prompt.toPlainText() == ''
    assert dialog.results_table.rowCount() == 0
    assert dialog.results_table.columnCount() == 0
    assert dialog.status_label.text() == 'Sin consulta ejecutada.'
    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()


def test_customer_code_is_not_formatted_as_decimal() -> None:
    _application()
    dialog = CustomerQueriesDialog()

    assert dialog._table_item('Cod.', 35).text() == '35'
    assert dialog._table_item('Kg', 35).text() == '35,00'
    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()


def test_customers_top_ribbon_contains_queries_button(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()

    button = page.findChild(QPushButton, "customerQueriesButton")

    assert button is not None
    assert button.text() == "Consultas"
    assert not button.icon().isNull()
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_agenda_calendar_uses_unclipped_popup_configuration(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()
    date_edit = QDateEdit(page)
    date_edit.setCalendarPopup(True)

    page._configure_agenda_calendar(date_edit)

    calendar = date_edit.calendarWidget()
    assert calendar.objectName() == "customerAgendaPopupCalendar"
    assert calendar.minimumWidth() == 340
    assert calendar.minimumHeight() == 272
    assert calendar.verticalHeaderFormat() == QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
    assert "QCalendarWidget#customerAgendaPopupCalendar QAbstractItemView::item" in page.styleSheet()
    page.close()
    page.deleteLater()
    QApplication.processEvents()
