from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCalendarWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from app.services.customer_dashboard_service import (
    DashboardActivityRow,
    DashboardIslandRow,
    DashboardReactivationRow,
    DashboardSnapshot,
)
from app.services.order_dashboard_service import (
    DashboardOrderRow,
    DashboardPendingArticleRow,
    DashboardOrdersStateRow,
    DashboardOrdersWarehouseRow,
    OrderDashboardSnapshot,
)
from app.services.sales_dashboard_service import (
    DashboardSalesCustomerRow,
    DashboardSalesIslandRow,
    DashboardSalesTypeRow,
    SalesDashboardSnapshot,
)
from app.services.warehouse_dashboard_service import (
    DashboardWarehouseMovementRow,
    DashboardWarehouseRiskRow,
    DashboardWarehouseStockRow,
    WarehouseDashboardSnapshot,
)
import app.ui.widgets.dashboard_page as dashboard_page_module
from app.ui.widgets.dashboard_page import DashboardCalendarDelegate, DashboardPage

_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


class _StubDashboardService:
    def load_snapshot(self) -> DashboardSnapshot:
        return DashboardSnapshot(
            pending_today=2,
            overdue=1,
            completed_today=3,
            customers_without_follow_up=4,
            today_items=[
                DashboardActivityRow(
                    agenda_id='ag-1', cliente_id='cli-1', cliente_codigo=101, cliente_nombre='Panaderia Norte',
                    isla_nombre='Gran Canaria', fecha_actividad=date(2026, 7, 21), fecha_seguimiento=None,
                    tipo='seguimiento', estado='pendiente', resumen='Revision comercial', detalle='Revisar consumo semanal',
                    prioridad='alta', responsable='Juan', created_at=datetime(2026, 7, 21, 8, 0, 0), updated_at=datetime(2026, 7, 21, 8, 0, 0),
                )
            ],
            upcoming_tomorrow=[], upcoming_next_three_days=[], upcoming_week=[],
            reactivation_rows=[
                DashboardReactivationRow(
                    cliente_id='cli-9', cliente_codigo=909, cliente_nombre='Cliente frio', isla_nombre='Tenerife',
                    last_contact=None, current_kg=15.0, previous_kg=40.0, delta_kg=-25.0, priority='Alta',
                )
            ],
            island_rows=[DashboardIslandRow(isla_nombre='Gran Canaria', pending=2, postponed=1, completed=0, total=3)],
            reactivation_metric_label='Variaci?n kg ? 2026-06 vs 2026-07',
            generated_at=datetime(2026, 7, 21, 9, 30, 0),
        )

    def list_all_activities(self):
        return [
            DashboardActivityRow(
                agenda_id='ag-1', cliente_id='cli-1', cliente_codigo=101, cliente_nombre='Panaderia Norte',
                isla_nombre='Gran Canaria', fecha_actividad=date(2026, 7, 21), fecha_seguimiento=None,
                tipo='seguimiento', estado='pendiente', resumen='Revision comercial', detalle='Revisar consumo semanal',
                prioridad='alta', responsable='Juan', created_at=datetime(2026, 7, 21, 8, 0, 0), updated_at=datetime(2026, 7, 21, 8, 0, 0),
            )
        ]


class _StubReportExportService:
    def __init__(self) -> None:
        self.default_calls: list[tuple[str, str, str]] = []
        self.export_calls: list[tuple[str, str, list[str], list[list[str]]]] = []
        self.agenda_pdf_calls: list[tuple[str, str, list[list[str]]]] = []

    def default_path(self, title: str, suffix: str, folder: str = '') -> Path:
        self.default_calls.append((title, suffix, folder))
        return Path('agenda_dashboard.pdf')

    def export_pdf(self, path: str, title: str, headers: list[str], rows: list[list[str]]) -> Path:
        self.export_calls.append((path, title, headers, rows))
        return Path(path)

    def export_dashboard_agenda_pdf(self, path: str, title: str, rows: list[list[str]]) -> Path:
        self.agenda_pdf_calls.append((path, title, rows))
        return Path(path)


class _StubCustomerRow:
    def __init__(self, cliente_id: str, cliente_codigo: int, cliente_nombre_comercial: str, activo: bool = True) -> None:
        self.cliente_id = cliente_id
        self.cliente_codigo = cliente_codigo
        self.cliente_nombre_comercial = cliente_nombre_comercial
        self.cliente_nombre_fiscal = cliente_nombre_comercial
        self.activo = activo


class _StubCustomerService:
    def list(self, _term: str):
        return [_StubCustomerRow('cli-1', 101, 'Panaderia Norte')]

    def get_agenda_activity(self, _agenda_id: str):
        return None

    def upsert_agenda_activity(self, _agenda_id: str, _payload: dict):
        return True

    def delete_agenda_activity(self, _agenda_id: str):
        return True


class _StubOrderDashboardService:
    def load_snapshot(self) -> OrderDashboardSnapshot:
        return OrderDashboardSnapshot(
            year=2026,
            total_orders=12,
            received_kg=15250.0,
            pending_kg=1875.5,
            incident_orders=2,
            recent_orders=[
                DashboardOrderRow(
                    pedido_id='ped-1', almacen_id='alm-1', almacen_nombre='Distribuidor Norte', pedido_fecha=date(2026, 7, 20),
                    pedido_numero='P-001', semana=30, ordered_kg=1000.0, received_kg=750.0, pending_kg=250.0, incident_kg=0.0,
                    status='parcial', last_receipt=date(2026, 7, 22),
                )
            ],
            pending_orders=[
                DashboardPendingArticleRow(
                    pedido_id='ped-2', pedido_fecha=date(2026, 7, 18), pedido_numero='P-002',
                    articulo_id='art-1', articulo_label='Harina Mix', article_name='Harina Mix', pending_kg=850.0,
                ),
                DashboardPendingArticleRow(
                    pedido_id='ped-3', pedido_fecha=date(2026, 7, 16), pedido_numero='P-003',
                    articulo_id='art-2', articulo_label='Mejorante Pan', article_name='Mejorante Pan', pending_kg=125.0,
                )
            ],
            warehouse_rows=[DashboardOrdersWarehouseRow(almacen_id='alm-2', almacen_nombre='Cliente Centro', open_orders=3, pending_kg=1250.0, last_receipt=date(2026, 7, 21))],
            state_rows=[DashboardOrdersStateRow(status='Pendiente', count=4, kg=2100.0)],
            generated_at=datetime(2026, 7, 24, 10, 15, 0),
        )



class _StubSalesDashboardService:
    def load_snapshot(self) -> SalesDashboardSnapshot:
        return SalesDashboardSnapshot(
            year=2026,
            previous_year=2025,
            total_kg=24500.0,
            delta_kg=-1250.5,
            delta_pct=-4.86,
            active_customers=87,
            active_islands=5,
            customers_down=12,
            customer_drop_rows=[
                DashboardSalesCustomerRow(
                    cliente_id='cli-31', cliente_codigo='431', cliente_nombre='Panaderia Azul', isla='Gran Canaria', cliente_tipo='Indirecto',
                    kg_prev=1500.0, kg_curr=950.0, delta_kg=-550.0, delta_pct=-36.67,
                )
            ],
            island_rows=[
                DashboardSalesIslandRow(
                    isla='Gran Canaria', customers=25, kg_prev=6400.0, kg_curr=7100.0, delta_kg=700.0, share_pct=28.98,
                )
            ],
            type_rows=[
                DashboardSalesTypeRow(
                    cliente_tipo='Indirecto', customers=54, kg_curr=18400.0, delta_kg=-950.0, share_pct=75.10,
                )
            ],
            zero_consumption_rows=[
                DashboardSalesCustomerRow(
                    cliente_id='cli-45', cliente_codigo='777', cliente_nombre='Cliente Dormido', isla='Lanzarote', cliente_tipo='Directo',
                    kg_prev=250.0, kg_curr=0.0, delta_kg=-250.0, delta_pct=-100.0,
                )
            ],
            generated_at=datetime(2026, 7, 24, 12, 45, 0),
        )


class _StubWarehouseDashboardService:
    def load_snapshot(self) -> WarehouseDashboardSnapshot:
        return WarehouseDashboardSnapshot(
            year=2026,
            month=7,
            total_stock_kg=2450.5,
            risk_items=2,
            entries_month_kg=820.0,
            outputs_month_kg=615.0,
            risk_rows=[
                DashboardWarehouseRiskRow(
                    almacen_id='alm-1', almacen_nombre='Central', articulo_id='art-1', referencia='1001', nombre='Harina Mix',
                    lote='L-01', caducidad=date(2026, 8, 4), stock_units=10.0, stock_kg=250.0, state='Caduca pronto',
                )
            ],
            warehouse_rows=[DashboardWarehouseStockRow(almacen_id='alm-1', almacen_nombre='Central', article_count=14, stock_kg=2450.5)],
            entry_rows=[DashboardWarehouseMovementRow(almacen_id='alm-1', almacen_nombre='Central', articulo_id='art-1', referencia='1001', nombre='Harina Mix', fecha=date(2026, 7, 20), units=5.0, kg=125.0, document_number='ALB-1')],
            output_rows=[DashboardWarehouseMovementRow(almacen_id='alm-1', almacen_nombre='Central', articulo_id='art-2', referencia='2002', nombre='Mejora Pan', fecha=date(2026, 7, 22), units=3.0, kg=75.0, document_number='SAL-1')],
            low_stock_threshold_units=4.0,
            generated_at=datetime(2026, 7, 21, 9, 30, 0),
        )


def test_dashboard_page_starts_in_agenda_mode() -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
        order_dashboard_service=_StubOrderDashboardService(),
        warehouse_dashboard_service=_StubWarehouseDashboardService(),
    )

    assert page.objectName() == 'dashboardPageRoot'
    assert page.title_label.text() == 'Agenda'
    assert page.new_activity_btn.objectName() == 'dashboardNewActivityButton'
    assert page.full_agenda_btn.objectName() == 'dashboardFullAgendaButton'
    assert page.reactivation_table.rowCount() == 1
    assert page.island_table.rowCount() == 1
    assert 'Última actualización:' in page.footer_label.text()
    assert not page.new_activity_btn.icon().isNull()
    assert not page.full_agenda_btn.icon().isNull()
    assert page.findChild(QWidget, 'dashboardSidebar').width() == 184
    kpi_cards = page.findChildren(QFrame, 'dashboardKpiCard')
    assert len(kpi_cards) == 16
    assert all(card.minimumHeight() == 104 and card.maximumHeight() == 104 for card in kpi_cards)
    assert page.findChild(QPushButton, 'dashboardPanelLinkButton') is None
    assert page.findChild(QPushButton, 'dashboardTodayPdfButton') is page.today_pdf_btn
    assert page.findChild(QPushButton, 'dashboardTodayPrintButton') is page.today_print_btn
    assert page.today_pdf_btn.width() == page.today_print_btn.width() == 96
    today_scroll = page.findChild(QScrollArea, 'dashboardTodayScrollArea')
    assert today_scroll is not None
    assert not today_scroll.isAncestorOf(page.today_panel_title)
    assert page.today_items_layout.alignment() == Qt.AlignmentFlag.AlignTop
    calendar = page.agenda_month_calendar
    assert page.findChild(QWidget, 'dashboardCalendarNavBlock') is None
    assert calendar.isNavigationBarVisible()
    assert calendar.isGridVisible()
    assert calendar.firstDayOfWeek() == Qt.DayOfWeek.Monday
    assert calendar.horizontalHeaderFormat() == QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
    assert calendar.verticalHeaderFormat() == QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers
    assert calendar.minimumWidth() == 320
    assert calendar.minimumHeight() == 220
    assert calendar.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert calendar.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    calendar_view = calendar.findChild(QAbstractItemView, 'qt_calendar_calendarview')
    assert isinstance(calendar_view.itemDelegate(), DashboardCalendarDelegate)
    assert DashboardCalendarDelegate.HEADER_TEXT_COLOR == '#FFFFFF'
    assert DashboardCalendarDelegate.SELECTED_BACKGROUND == '#F1F5F9'
    assert DashboardCalendarDelegate.SELECTED_BORDER == '#475569'
    assert DashboardCalendarDelegate.TODAY_BACKGROUND == '#FDE68A'
    assert DashboardCalendarDelegate.TODAY_BORDER == '#F59E0B'
    summary_chips = page.findChildren(QFrame, 'dashboardCalendarSummaryChip')
    assert len(summary_chips) == 3
    assert all(chip.minimumHeight() == 34 and chip.maximumHeight() == 34 for chip in summary_chips)
    summary_titles = page.findChildren(QLabel, 'dashboardCalendarSummaryTitle')
    assert [label.text() for label in summary_titles] == ['Pendientes', 'Hechas', 'Vencidas']
    assert all(label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Minimum for label in summary_titles)
    assert all(label.minimumSizeHint().width() > 0 for label in summary_titles)
    style_sheet = page.styleSheet()
    assert 'QFrame#dashboardHeader { background-color: transparent; border: none; }' in style_sheet
    assert 'QStackedWidget#dashboardContentStack { background-color: transparent; border: none; }' in style_sheet
    assert 'QPushButton#dashboardTodayPdfButton { background-color: #2563EB; }' in style_sheet
    assert 'QPushButton#dashboardTodayPrintButton { background-color: #16A34A; }' in style_sheet
    assert 'QLabel#dashboardCalendarSummaryTitle { color: #000000;' in style_sheet
    assert 'QLabel#dashboardCalendarSummaryValue { color: #000000;' in style_sheet
    assert 'color: #000000;\n                font-size: 13px;' in style_sheet
    assert page.minimumSizeHint().width() <= 1180

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_page_selects_day_and_updates_title() -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
        order_dashboard_service=_StubOrderDashboardService(),
        warehouse_dashboard_service=_StubWarehouseDashboardService(),
    )

    page.set_selected_date(date(2026, 7, 21))

    assert page.today_panel_title.text() == 'Agenda del 21/07/2026'
    assert len(page._agenda_rows_for_date(date(2026, 7, 21))) == 1
    assert page._agenda_day_tone(page._agenda_rows_for_date(date(2026, 7, 21)), today_value=date(2026, 7, 20)) == 'blue'

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_page_keeps_activity_on_its_planned_date_when_follow_up_exists() -> None:
    _application()
    service = _StubDashboardService()
    followed_up = DashboardActivityRow(
        agenda_id='ag-2', cliente_id='cli-2', cliente_codigo=586, cliente_nombre='NPANADERIA',
        isla_nombre='Tenerife', fecha_actividad=date(2026, 7, 18), fecha_seguimiento=date(2026, 7, 23),
        tipo='seguimiento', estado='hecho', resumen='Concretar reunión', detalle='', prioridad='normal',
        responsable='Ana', created_at=datetime(2026, 7, 18, 8, 0, 0), updated_at=datetime(2026, 7, 23, 8, 0, 0),
    )
    service.list_all_activities = lambda: [followed_up]
    page = DashboardPage(
        customer_service=_StubCustomerService(), dashboard_service=service,
        order_dashboard_service=_StubOrderDashboardService(), warehouse_dashboard_service=_StubWarehouseDashboardService(),
    )

    page.set_selected_date(date(2026, 7, 18))

    cards = page.findChildren(QFrame, 'dashboardActivityCard')
    assert len(cards) == 1
    assert isinstance(cards[0].layout(), QHBoxLayout)
    assert cards[0].findChild(QLabel, 'dashboardActivityCustomer').text() == '586 · NPANADERIA'
    assert cards[0].findChild(QLabel, 'dashboardActivitySummary').text() == 'Concretar reunión'
    assert cards[0].findChild(QLabel, 'dashboardActivityState').text() == 'Hecha'
    assert page.today_pdf_btn.isEnabled()
    assert page.today_print_btn.isEnabled()
    assert page._today_report_data() == (
        'Agenda del 18/07/2026',
        ['Fecha', 'Cliente', 'Contenido', 'Estado'],
        [['18/07/2026', '586 · NPANADERIA', 'Concretar reunión', 'Hecha']],
    )
    assert '586 · NPANADERIA' in page._today_report_html()
    assert page._agenda_day_tone(page._agenda_rows_for_date(date(2026, 7, 18)), today_value=date(2026, 7, 23)) == 'green'
    assert page._agenda_rows_for_date(date(2026, 7, 23)) == []

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_page_exports_the_visible_agenda_selection_to_pdf(monkeypatch) -> None:
    _application()
    report_service = _StubReportExportService()
    page = DashboardPage(
        customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService(),
        order_dashboard_service=_StubOrderDashboardService(), warehouse_dashboard_service=_StubWarehouseDashboardService(),
        report_export_service=report_service,
    )
    page.set_selected_date(date(2026, 7, 21))
    preview: dict[str, object] = {}

    class _CapturedPreviewDialog:
        def __init__(self, **kwargs) -> None:
            preview.update(kwargs)

        def exec(self) -> int:
            preview['executed'] = True
            return 0

    monkeypatch.setattr(dashboard_page_module, 'DashboardAgendaPdfPreviewDialog', _CapturedPreviewDialog)

    page.today_pdf_btn.click()

    assert preview['report_export_service'] is report_service
    assert preview['title'] == 'Agenda del 21/07/2026'
    assert preview['headers'] == ['Fecha', 'Cliente', 'Contenido', 'Estado']
    assert preview['rows'] == [[
        '21/07/2026',
        '101 · Panaderia Norte',
        'Revision comercial — Revisar consumo semanal',
        'Pendiente',
    ]]
    assert preview['parent'] is page
    assert preview['executed'] is True
    printed: dict[str, object] = {}

    class _AcceptedPrintDialog:
        class DialogCode:
            Accepted = 1

        def __init__(self, printer, parent) -> None:
            printed['printer'] = printer
            printed['parent'] = parent

        def exec(self) -> int:
            return self.DialogCode.Accepted

    class _CapturedTextDocument:
        def __init__(self, parent) -> None:
            printed['document_parent'] = parent

        def setHtml(self, value: str) -> None:
            printed['html'] = value

        def print_(self, printer) -> None:
            printed['printed_with'] = printer

    monkeypatch.setattr(dashboard_page_module, 'QPrintDialog', _AcceptedPrintDialog)
    monkeypatch.setattr(dashboard_page_module, 'QTextDocument', _CapturedTextDocument)

    page.today_print_btn.click()

    assert printed['printed_with'] is printed['printer']
    assert '101 · Panaderia Norte' in str(printed['html'])
    assert 'Revision comercial' in str(printed['html'])
    page._render_activity_cards([], empty_text='Sin actividades')
    assert not page.today_pdf_btn.isEnabled()
    assert not page.today_print_btn.isEnabled()

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_agenda_pdf_preview_can_save_or_cancel(monkeypatch) -> None:
    _application()
    report_service = _StubReportExportService()
    long_content = 'Revision comercial con todos los acuerdos y próximos pasos. ' * 12
    dialog = dashboard_page_module.DashboardAgendaPdfPreviewDialog(
        report_export_service=report_service,
        title='Agenda del 21/07/2026',
        headers=['Fecha', 'Cliente', 'Contenido', 'Estado'],
        rows=[['21/07/2026', '101 · Panaderia Norte', long_content, 'Pendiente']],
    )
    dialog.show()
    QApplication.processEvents()
    monkeypatch.setattr(
        dashboard_page_module.QFileDialog,
        'getSaveFileName',
        lambda *_args, **_kwargs: ('agenda_guardada.pdf', 'PDF (*.pdf)'),
    )
    monkeypatch.setattr(dashboard_page_module.QMessageBox, 'information', lambda *_args, **_kwargs: None)

    cards = dialog.findChildren(QFrame, 'dashboardAgendaPdfPreviewCard')
    assert len(cards) == 1
    assert cards[0].findChild(QLabel, 'dashboardAgendaPdfPreviewDate').text() == '21/07/2026'
    assert cards[0].findChild(QLabel, 'dashboardAgendaPdfPreviewCustomer').text() == '101 · Panaderia Norte'
    content_label = cards[0].findChild(QLabel, 'dashboardAgendaPdfPreviewContent')
    assert content_label.text() == long_content
    assert content_label.wordWrap()
    assert content_label.height() > content_label.fontMetrics().height()
    state_label = cards[0].findChild(QLabel, 'dashboardAgendaPdfPreviewState')
    assert state_label.text() == 'Pendiente'
    assert state_label.property('tone') == 'pending'
    assert state_label.alignment() & Qt.AlignmentFlag.AlignRight
    assert dialog.save_btn.text() == 'Guardar'
    assert dialog.cancel_btn.text() == 'Cancelar'
    dialog.save_btn.click()

    assert report_service.default_calls == [('Agenda del 21/07/2026', 'pdf', 'agenda_dashboard')]
    assert report_service.agenda_pdf_calls == [(
        'agenda_guardada.pdf',
        'Agenda del 21/07/2026',
        [['21/07/2026', '101 · Panaderia Norte', long_content, 'Pendiente']],
    )]

    cancel_dialog = dashboard_page_module.DashboardAgendaPdfPreviewDialog(
        report_export_service=_StubReportExportService(),
        title='Agenda del 21/07/2026',
        headers=['Fecha', 'Cliente', 'Contenido', 'Estado'],
        rows=[['21/07/2026', '101 · Panaderia Norte', 'Revision comercial', 'Pendiente']],
    )
    cancel_dialog.cancel_btn.click()
    assert cancel_dialog.result() == dashboard_page_module.QDialog.DialogCode.Rejected
    QApplication.processEvents()


def test_dashboard_page_week_number_click_lists_the_whole_week() -> None:
    _application()
    service = _StubDashboardService()
    week_rows = [
        DashboardActivityRow(
            agenda_id=f'ag-{day}', cliente_id=f'cli-{day}', cliente_codigo=100 + day, cliente_nombre=f'Cliente {day}',
            isla_nombre='Gran Canaria', fecha_actividad=date(2026, 7, day), fecha_seguimiento=None,
            tipo='seguimiento', estado='pendiente', resumen=f'Actividad {day}', detalle='', prioridad='normal',
            responsable='Ana', created_at=datetime(2026, 7, day, 8, 0, 0), updated_at=datetime(2026, 7, day, 8, 0, 0),
        )
        for day in (20, 22, 26, 27)
    ]
    service.list_all_activities = lambda: week_rows
    page = DashboardPage(
        customer_service=_StubCustomerService(), dashboard_service=service,
        order_dashboard_service=_StubOrderDashboardService(), warehouse_dashboard_service=_StubWarehouseDashboardService(),
    )
    calendar = page.agenda_month_calendar
    page.resize(1180, 850)
    page.show()
    calendar.setCurrentPage(2026, 7)
    QApplication.processEvents()
    calendar_view = calendar.findChild(QAbstractItemView, 'qt_calendar_calendarview')
    delegate = calendar_view.itemDelegate()
    week_row = next(
        row for row in range(1, 7)
        if delegate._date_for_index(row, 1) == QDate(2026, 7, 20)
    )

    week_index = calendar_view.model().index(week_row, 0)
    QTest.mouseClick(
        calendar_view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        calendar_view.visualRect(week_index).center(),
    )
    QApplication.processEvents()

    assert page.today_panel_title.text() == 'Agenda semana 30 · 20/07/2026 - 26/07/2026'
    assert len(page.findChildren(QFrame, 'dashboardActivityCard')) == 3
    assert [label.text() for label in page.findChildren(QLabel, 'dashboardActivitySummary')] == [
        'Actividad 20', 'Actividad 22', 'Actividad 26'
    ]

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_page_can_switch_to_orders_mode() -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
        order_dashboard_service=_StubOrderDashboardService(),
        warehouse_dashboard_service=_StubWarehouseDashboardService(),
    )

    page._set_dashboard_mode('pedidos')

    assert page.title_label.text() == 'Pedidos'
    assert page.dashboard_stack.currentWidget().objectName() == 'dashboardOrdersView'
    assert page.orders_recent_table.rowCount() == 1
    assert page.orders_recent_table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows
    assert page.orders_recent_table.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection
    assert [
        page.orders_recent_table.horizontalHeaderItem(col).text()
        for col in range(page.orders_recent_table.columnCount())
    ] == ['Pedido', 'Almacén', 'Sem', 'Fecha', 'Kg pedido', 'Kg recibido', 'Kg pend.']
    assert page._recent_order_id_for_row(0) == 'ped-1'
    assert page.orders_recent_table.item(0, 2).text() == '30'
    for col in (4, 5, 6):
        assert page.orders_recent_table.item(0, col).textAlignment() == (
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
    assert page.orders_pending_table.rowCount() == 2
    assert page.orders_pending_table.horizontalHeaderItem(2).text() == 'Artículo'
    assert page.orders_pending_table.isSortingEnabled()
    assert page.orders_pending_table.item(0, 0).text() == '18/07/2026'
    assert page.orders_pending_table.item(1, 0).text() == '16/07/2026'
    assert page.orders_pending_table.item(0, 2).text() == 'Harina Mix'
    assert page.orders_pending_table.item(0, 3).textAlignment() == (
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    assert page.orders_warehouse_table.rowCount() == 1
    assert page.orders_state_table.rowCount() == 1
    assert page.orders_kpi_labels['pending_kg'].text() == '1.875,50'
    assert page.orders_kpi_units['pending_kg'].text() == 'kg'
    assert not page.orders_kpi_units['pending_kg'].isHidden()

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_recent_orders_hover_paints_complete_row() -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
        order_dashboard_service=_StubOrderDashboardService(),
        warehouse_dashboard_service=_StubWarehouseDashboardService(),
    )

    page._set_dashboard_mode('pedidos')
    page._set_table_hover_row(page.orders_recent_table, 0)

    assert page.orders_recent_table.property('hoverRow') == 0

    page._set_table_hover_row(page.orders_recent_table, -1)

    assert page.orders_recent_table.property('hoverRow') == -1

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_recent_order_navigation_selects_order_page_row() -> None:
    _application()
    selected_pages: list[int] = []
    selected_orders: list[str] = []

    class _OrdersPage(QWidget):
        def _select_by_id(self, pedido_id: str) -> None:
            selected_orders.append(pedido_id)

    class _Pages:
        def widget(self, index: int) -> QWidget:
            assert index == 1
            return orders_page

    class _Window(QMainWindow):
        page_names = ['Inicio', 'Pedidos']
        pages = _Pages()

        def _set_current_page(self, index: int) -> None:
            selected_pages.append(index)

    orders_page = _OrdersPage()
    window = _Window()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
        order_dashboard_service=_StubOrderDashboardService(),
        warehouse_dashboard_service=_StubWarehouseDashboardService(),
    )
    window.setCentralWidget(page)

    page._open_order_from_dashboard('order-1')

    assert selected_pages == [1]
    assert selected_orders == ['order-1']

    page.close()
    window.close()
    page.deleteLater()
    orders_page.deleteLater()
    window.deleteLater()
    QApplication.processEvents()


def test_dashboard_page_can_switch_to_warehouse_mode() -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
        order_dashboard_service=_StubOrderDashboardService(),
        warehouse_dashboard_service=_StubWarehouseDashboardService(),
    )

    page._set_dashboard_mode('almacen')

    assert page.title_label.text() == 'Almacen'
    assert page.dashboard_stack.currentWidget().objectName() == 'dashboardWarehouseView'
    assert page.warehouse_risk_table.rowCount() == 1
    assert page.warehouse_stock_table.rowCount() == 1
    assert page.warehouse_entries_table.rowCount() == 1
    assert page.warehouse_outputs_table.rowCount() == 1
    assert page.warehouse_kpi_labels['total_stock_kg'].text() == '2.450,50 kg'

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_page_can_switch_to_sales_mode() -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
        sales_dashboard_service=_StubSalesDashboardService(),
    )

    page._set_dashboard_mode('ventas')

    assert page.title_label.text() == 'Ventas'
    assert page.dashboard_stack.currentWidget().objectName() == 'dashboardSalesView'
    assert page.sales_kpi_labels['total_kg'].text() == '24.500,00'
    assert page.sales_kpi_labels['delta_kg'].text() == '-1.250,50'
    assert page.sales_kpi_labels['active_customers'].text() == '87'
    assert page.sales_kpi_labels['active_islands'].text() == '5'
    assert page.sales_drops_table.rowCount() == 1
    assert page.sales_drops_table.item(0, 0).text() == '431 · Panaderia Azul'
    assert page.sales_islands_table.rowCount() == 1
    assert page.sales_types_table.rowCount() == 1
    assert page.sales_zero_table.rowCount() == 1
    assert 'Ventas 2026 vs 2025' in page.footer_label.text()

    page.close()
    page.deleteLater()
    QApplication.processEvents()

def test_dashboard_page_agenda_actions_open_real_dialog_paths(monkeypatch) -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
    )

    calls: list[str] = []

    class _FakeAgendaDialog:
        def __init__(self, *args, **kwargs):
            calls.append('new')

        def exec(self):
            return dashboard_page_module.QDialog.DialogCode.Accepted

    class _FakeOverviewDialog:
        changed = True

        def __init__(self, *args, **kwargs):
            calls.append('overview')

        def exec(self):
            return dashboard_page_module.QDialog.DialogCode.Accepted

    monkeypatch.setattr(dashboard_page_module, 'DashboardAgendaDialog', _FakeAgendaDialog)
    monkeypatch.setattr(dashboard_page_module, 'DashboardAgendaOverviewDialog', _FakeOverviewDialog)

    page._handle_primary_action()
    page._handle_secondary_action()

    assert calls == ['new', 'overview']

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_activity_card_right_click_opens_edit_dialog(monkeypatch) -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
    )
    page.set_selected_date(date(2026, 7, 21))
    page.resize(1180, 850)
    page.show()
    QApplication.processEvents()

    card = page.findChild(QFrame, 'dashboardActivityCard')
    assert card is not None
    assert card.property('agendaId') == 'ag-1'
    for label_name in ('dashboardActivityCustomer', 'dashboardActivitySummary', 'dashboardActivityState'):
        label = card.findChild(QLabel, label_name)
        assert label is not None
        assert label.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    dialog_calls: list[str] = []
    dialog_result = {'value': dashboard_page_module.QDialog.DialogCode.Rejected}
    reload_calls: list[bool] = []

    class _FakeAgendaDialog:
        def __init__(self, *args, **kwargs):
            dialog_calls.append(kwargs.get('agenda_id', ''))

        def exec(self):
            return dialog_result['value']

    monkeypatch.setattr(dashboard_page_module, 'DashboardAgendaDialog', _FakeAgendaDialog)
    monkeypatch.setattr(page, 'reload', lambda: reload_calls.append(True))

    QTest.mouseClick(
        card,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
        card.rect().center(),
    )
    QApplication.processEvents()

    assert dialog_calls == ['ag-1']
    assert reload_calls == []

    dialog_result['value'] = dashboard_page_module.QDialog.DialogCode.Accepted
    QTest.mouseClick(
        card,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
        card.rect().center(),
    )
    QApplication.processEvents()

    assert dialog_calls == ['ag-1', 'ag-1']
    assert reload_calls == [True]

    page.close()
    page.deleteLater()
    QApplication.processEvents()


