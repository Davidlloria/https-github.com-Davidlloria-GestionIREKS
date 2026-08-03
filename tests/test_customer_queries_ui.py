from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView, QCalendarWidget, QDateEdit, QPushButton

from app.ui.widgets.customer_queries_dialog import CustomerQueriesDialog
from app.ui.widgets.customers_page import AgendaCalendarDelegate, CustomersPage

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


def test_customers_search_row_has_counter(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()

    assert page.search_input.minimumWidth() == 220
    assert page.search_input.maximumWidth() == 220
    assert page.search_counter_label.objectName() == "customerSearchCounterLabel"
    assert page.search_counter_label.text() == "0/0"

    page._update_search_counter(12, 720)

    assert page.search_counter_label.text() == "12/720"
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_customer_merge_summary_lists_dependencies(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()
    preview = SimpleNamespace(
        source_label="1 - Origen",
        target_label="2 - Destino",
        counts={
            "contactos": 1,
            "recetas": 2,
            "agenda": 3,
            "asistentes": 4,
            "ventas_clientes": 5,
        },
    )

    text = page._customer_merge_summary_text(preview)

    assert "Origen: 1 - Origen" in text
    assert "Destino: 2 - Destino" in text
    assert "- Ventas clientes: 5" in text
    assert "se eliminara el cliente origen" in text
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
    assert calendar.firstDayOfWeek() == Qt.DayOfWeek.Monday
    assert calendar.isGridVisible()
    assert calendar.horizontalHeaderFormat() == QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
    assert calendar.verticalHeaderFormat() == QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers
    assert calendar.headerTextFormat().background().color().name() == "#5b8def"
    assert calendar.weekdayTextFormat(Qt.DayOfWeek.Sunday).foreground().color().name() == "#d94c5c"
    calendar_view = calendar.findChild(QAbstractItemView, "qt_calendar_calendarview")
    assert isinstance(calendar_view.itemDelegate(), AgendaCalendarDelegate)
    assert "QCalendarWidget#customerAgendaPopupCalendar QAbstractItemView::item" in page.styleSheet()
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_customer_agenda_type_options_include_demo(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()

    options = page._agenda_type_options()
    assert ("visita", "Visita") in options
    assert ("visita_realizada", "Visita realizada") not in options
    assert ("visita_prevista", "Visita prevista") not in options
    assert ("demo", "Demo") in options
    assert page._agenda_type_label("visita_realizada") == "Visita"
    assert page._agenda_type_label("visita_prevista") == "Visita"
    assert page._agenda_type_label("demo") == "Demo"

    page._agenda_filter_type.setCurrentIndex(page._agenda_filter_type.findData("visita"))
    assert page._agenda_matches_filters(SimpleNamespace(tipo="visita_realizada", estado="pendiente", fecha_actividad=None))
    assert page._agenda_matches_filters(SimpleNamespace(tipo="visita_prevista", estado="hecho", fecha_actividad=None))

    page.close()
    page.deleteLater()
    QApplication.processEvents()
