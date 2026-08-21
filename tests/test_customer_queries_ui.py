from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView, QCalendarWidget, QCheckBox, QDateEdit, QFrame, QLabel, QPushButton, QWidget

from app.ui.widgets.customer_queries_dialog import CustomerQueriesDialog
from app.services.customer_query_service import CustomerQueryResult
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
    assert dialog.excel_button.objectName() == "customerQueryExcelButton"
    assert dialog.excel_button.text() == "Excel"
    assert not dialog.excel_button.icon().isNull()
    assert not dialog.excel_button.isEnabled()
    assert dialog.pdf_button.objectName() == "customerQueryPdfButton"
    assert dialog.pdf_button.text() == "Pdf"
    assert not dialog.pdf_button.icon().isNull()
    assert not dialog.pdf_button.isEnabled()
    assert dialog.close_button.objectName() == "customerQueriesCloseButton"
    assert dialog.clear_button.objectName() == 'customerQueryClearButton'
    assert dialog.findChildren(QPushButton, 'customerQueryExampleButton') == []
    assert '#60A5FA' in dialog.run_button.styleSheet()
    assert '#16A34A' in dialog.excel_button.styleSheet()
    assert '#DC2626' in dialog.pdf_button.styleSheet()
    assert '#F59E0B' in dialog.clear_button.styleSheet()
    assert '#F3F4F6' in dialog.excel_button.styleSheet()
    assert '#374151' in dialog.pdf_button.styleSheet()
    assert '#9CA3AF' in dialog.clear_button.styleSheet()
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
    assert not dialog.excel_button.isEnabled()
    assert not dialog.pdf_button.isEnabled()
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


class _StubReportExportService:
    def __init__(self) -> None:
        self.calls = []

    def default_path(self, title: str, suffix: str, folder: str = "listados_clientes") -> Path:
        return Path(f"export.{suffix}")

    def export_excel(self, path: str, title: str, headers: list[str], rows: list[list[str]], sheet_title: str = "Listado clientes") -> Path:
        self.calls.append(("excel", path, title, headers, rows, sheet_title))
        return Path(path)

    def export_pdf(self, path: str, title: str, headers: list[str], rows: list[list[str]]) -> Path:
        self.calls.append(("pdf", path, title, headers, rows))
        return Path(path)


def test_customer_query_exports_visible_results(monkeypatch, tmp_path) -> None:
    _application()
    export_service = _StubReportExportService()
    dialog = CustomerQueriesDialog(report_export_service=export_service)
    messages = []
    monkeypatch.setattr(
        "app.ui.widgets.customer_queries_dialog.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "consulta.xlsx"), ""),
    )
    monkeypatch.setattr(
        "app.ui.widgets.customer_queries_dialog.QMessageBox.information",
        lambda *args, **kwargs: messages.append(args),
    )
    dialog._show_result(
        CustomerQueryResult(
            status="ready",
            title="Consulta ventas",
            headers=["Nombre comercial", "Kg"],
            rows=[["Cliente Uno", 12.5]],
            source="cálculo local",
        )
    )

    assert dialog.excel_button.isEnabled()
    assert dialog.pdf_button.isEnabled()

    dialog._export_excel()

    monkeypatch.setattr(
        "app.ui.widgets.customer_queries_dialog.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "consulta.pdf"), ""),
    )
    dialog._export_pdf()

    assert export_service.calls == [
        (
            "excel",
            str(tmp_path / "consulta.xlsx"),
            "Consulta ventas",
            ["Nombre comercial", "Kg"],
            [["Cliente Uno", 12.5]],
            "Consulta clientes",
        ),
        (
            "pdf",
            str(tmp_path / "consulta.pdf"),
            "Consulta ventas",
            ["Nombre comercial", "Kg"],
            [["Cliente Uno", 12.5]],
        ),
    ]
    assert messages
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


def test_customers_catalog_uses_the_standard_detail_header(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()

    header = page.findChild(QFrame, "customersCatalogHeader")
    title = page.findChild(QLabel, "customersCatalogHeaderTitle")
    icon = page.findChild(QLabel, "customersCatalogHeaderIcon")

    assert header is not None
    assert header.property("uiRole") == "detailHeader"
    assert header.height() == 38
    assert title is not None
    assert title.text() == "CLIENTES"
    assert icon is not None
    assert not icon.pixmap().isNull()
    panel = page.findChild(QWidget, "customersLeftPanel")
    body = page.findChild(QWidget, "customersCatalogBody")
    page.resize(1360, 820)
    page.show()
    QApplication.processEvents()
    assert panel is not None
    assert body is not None
    assert header.geometry().top() == panel.contentsRect().top()
    assert header.geometry().left() == panel.contentsRect().left()
    assert header.width() == panel.contentsRect().width()
    assert "QWidget#customersCatalogBody" in page.styleSheet()
    assert "QWidget#customersCatalogBody {\n                background: #FFFFFF;\n                border: 1px solid #D7DEE8;" in page.styleSheet()
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_customer_detail_card_uses_the_standard_detail_header(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()

    header = page.findChild(QFrame, "customerDetailHeader")
    title = page.findChild(QLabel, "customerDetailHeaderTitle")
    icon = page.findChild(QLabel, "customerDetailHeaderIcon")
    body = page.findChild(QWidget, "customerDetailBody")

    assert header is not None
    assert header.property("uiRole") == "detailHeader"
    assert header.height() == 38
    assert title is not None
    assert title.text() == "DETALLE DEL CLIENTE"
    assert icon is not None
    assert not icon.pixmap().isNull()
    assert body is not None
    assert body.layout().contentsMargins().left() == 4
    assert body.layout().contentsMargins().right() == 4
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_customer_detail_rightmost_fields_keep_a_four_pixel_margin(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()
    page.resize(1360, 820)
    page.show()
    QApplication.processEvents()

    panel = page.left_detail_panel
    expected_right = panel.width() - 5
    for field in (
        page.detail_nombre_comercial,
        page.detail_nombre_fiscal,
        page.detail_municipio,
        page.detail_localidad,
    ):
        assert field.geometry().right() == expected_right

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_customer_classification_card_uses_the_standard_detail_header(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()

    header = page.findChild(QFrame, "customerClassificationHeader")
    title = page.findChild(QLabel, "customerClassificationHeaderTitle")
    icon = page.findChild(QLabel, "customerClassificationHeaderIcon")
    body = page.findChild(QWidget, "customerClassificationBody")

    assert header is not None
    assert header.property("uiRole") == "detailHeader"
    assert header.height() == 38
    assert title is not None
    assert title.text() == "CLASIFICACIÓN DEL CLIENTE"
    assert icon is not None
    assert not icon.pixmap().isNull()
    assert body is not None
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_customer_classification_panel_keeps_persistence_controls_hidden(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()

    placeholder = page.findChild(QCheckBox, "otros_placeholder")

    assert placeholder is not None
    assert placeholder.isEnabled()
    assert page.detail_prospeccion_si.isHidden()
    assert page.detail_prospeccion_no.isHidden()
    assert page.lbl_prospeccion.isHidden()
    assert page.right_detail_panel.layout() is not None
    assert len(page.tipo_checks) == 7

    page.tipo_checks["PANADERIA"].setChecked(True)
    page.tipo_checks["PASTELERIA"].setChecked(True)
    placeholder.setChecked(True)
    assert placeholder.isChecked()
    assert not page.tipo_checks["PANADERIA"].isChecked()
    assert not page.tipo_checks["PASTELERIA"].isChecked()

    page.tipo_checks["HOTEL"].setChecked(True)
    assert page.tipo_checks["HOTEL"].isChecked()
    assert not placeholder.isChecked()

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_customer_list_uses_the_other_icon_for_the_other_activity(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()
    customer = SimpleNamespace(cliente_actividad="OTROS")

    assert page._customer_icon(customer) == ""
    assert not page._customer_list_icon(customer).isNull()

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


def test_customer_merge_filter_normalizes_text(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()

    assert page._normalize_filter_text("  CADELSA Lanzaróte  ") == "cadelsa lanzarote"
    assert page._normalize_filter_text("518 - CADELSA LZA") == "518 - cadelsa lza"

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
