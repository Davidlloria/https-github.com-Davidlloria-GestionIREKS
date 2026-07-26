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
from app.services.warehouse_dashboard_service import (
    DashboardWarehouseMovementRow,
    DashboardWarehouseRiskRow,
    DashboardWarehouseStockRow,
    WarehouseDashboardSnapshot,
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
    page = DashboardPage(customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService(), warehouse_dashboard_service=_StubWarehouseDashboardService())

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
    page = DashboardPage(customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService(), warehouse_dashboard_service=_StubWarehouseDashboardService())

    page.set_selected_date(date(2026, 7, 21))

    assert page.today_panel_title.text() == 'Agenda del 21/07/2026'
    assert len(page._agenda_rows_for_date(date(2026, 7, 21))) == 1
    assert page._agenda_day_tone(page._agenda_rows_for_date(date(2026, 7, 21)), today_value=date(2026, 7, 20)) == 'blue'

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_page_can_switch_to_warehouse_mode() -> None:
    _application()
    page = DashboardPage(customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService(), warehouse_dashboard_service=_StubWarehouseDashboardService())

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
