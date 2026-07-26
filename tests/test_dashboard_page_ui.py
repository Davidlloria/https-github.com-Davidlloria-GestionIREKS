from __future__ import annotations

import os
from datetime import date, datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

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
from app.ui.widgets.dashboard_page import DashboardPage

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
            reactivation_metric_label='Variación kg · 2026-06 vs 2026-07',
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


class _StubCustomerService:
    def list(self, _term: str):
        return []

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


def test_dashboard_page_starts_in_agenda_mode() -> None:
    _application()
    page = DashboardPage(customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService(), order_dashboard_service=_StubOrderDashboardService())

    assert page.objectName() == 'dashboardPageRoot'
    assert page.title_label.text() == 'Agenda'
    assert page.new_activity_btn.objectName() == 'dashboardNewActivityButton'
    assert page.full_agenda_btn.objectName() == 'dashboardFullAgendaButton'
    assert page.reactivation_table.rowCount() == 1
    assert page.island_table.rowCount() == 1
    assert 'Variación kg' in page.footer_label.text()
    assert not page.new_activity_btn.icon().isNull()
    assert not page.full_agenda_btn.icon().isNull()
    assert page.findChild(QWidget, 'dashboardSidebar').width() == 184
    assert page.minimumSizeHint().width() <= 1180

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_page_selects_day_and_updates_title() -> None:
    _application()
    page = DashboardPage(customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService(), order_dashboard_service=_StubOrderDashboardService())

    page.set_selected_date(date(2026, 7, 21))

    assert page.today_panel_title.text() == 'Agenda del 21/07/2026'
    assert len(page._agenda_rows_for_date(date(2026, 7, 21))) == 1
    assert page._agenda_day_tone(page._agenda_rows_for_date(date(2026, 7, 21)), today_value=date(2026, 7, 20)) == 'blue'

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_page_can_switch_to_orders_mode() -> None:
    _application()
    page = DashboardPage(customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService(), order_dashboard_service=_StubOrderDashboardService())

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
