from __future__ import annotations

import os
from datetime import date, datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView, QCalendarWidget, QFrame, QLabel, QSizePolicy, QWidget

from app.services.customer_dashboard_service import (
    DashboardActivityRow,
    DashboardIslandRow,
    DashboardReactivationRow,
    DashboardSnapshot,
)
from app.services.order_dashboard_service import (
    DashboardOrderRow,
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
                DashboardOrderRow(
                    pedido_id='ped-2', almacen_id='alm-2', almacen_nombre='Cliente Centro', pedido_fecha=date(2026, 7, 18),
                    pedido_numero='P-002', semana=29, ordered_kg=850.0, received_kg=0.0, pending_kg=850.0, incident_kg=0.0,
                    status='pendiente', last_receipt=None,
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
    assert 'Variaci?n kg' in page.footer_label.text()
    assert not page.new_activity_btn.icon().isNull()
    assert not page.full_agenda_btn.icon().isNull()
    assert page.findChild(QWidget, 'dashboardSidebar').width() == 184
    kpi_cards = page.findChildren(QFrame, 'dashboardKpiCard')
    assert len(kpi_cards) == 16
    assert all(card.minimumHeight() == 104 and card.maximumHeight() == 104 for card in kpi_cards)
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
    assert page.orders_pending_table.rowCount() == 1
    assert page.orders_warehouse_table.rowCount() == 1
    assert page.orders_state_table.rowCount() == 1
    assert page.orders_kpi_labels['pending_kg'].text() == '1.875,50 kg'

    page.close()
    page.deleteLater()
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
    assert page.sales_drops_table.item(0, 0).text() == '431 Â· Panaderia Azul'
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


