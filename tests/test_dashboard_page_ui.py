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


class _StubCustomerService:
    def list(self, _term: str):
        return []


def test_dashboard_page_starts_in_agenda_mode() -> None:
    _application()
    page = DashboardPage(customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService())

    assert page.objectName() == 'dashboardPageRoot'
    assert page.title_label.text() == 'Agenda'
    assert page.new_activity_btn.objectName() == 'dashboardNewActivityButton'
    assert page.full_agenda_btn.objectName() == 'dashboardFullAgendaButton'
    assert page.reactivation_table.rowCount() == 1
    assert page.island_table.rowCount() == 1
    assert 'Variaci?n kg' in page.footer_label.text()

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_dashboard_page_selects_day_and_updates_title() -> None:
    _application()
    page = DashboardPage(customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService())

    page.set_selected_date(date(2026, 7, 21))

    assert page.today_panel_title.text() == 'Agenda del 21/07/2026'

    page.close()
    page.deleteLater()
    QApplication.processEvents()
