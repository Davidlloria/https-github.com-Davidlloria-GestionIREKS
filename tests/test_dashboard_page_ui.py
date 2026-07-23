from __future__ import annotations

import os
from datetime import date, datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

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
                    agenda_id="ag-1",
                    cliente_id="cli-1",
                    cliente_codigo=101,
                    cliente_nombre="Panaderia Norte",
                    isla_nombre="Gran Canaria",
                    fecha_actividad=date(2026, 7, 21),
                    fecha_seguimiento=None,
                    tipo="seguimiento",
                    estado="pendiente",
                    resumen="Revision comercial",
                    detalle="Revisar consumo semanal",
                    prioridad="alta",
                    responsable="Juan",
                    created_at=datetime(2026, 7, 21, 8, 0, 0),
                    updated_at=datetime(2026, 7, 21, 8, 0, 0),
                )
            ],
            upcoming_tomorrow=[],
            upcoming_next_three_days=[],
            upcoming_week=[],
            reactivation_rows=[
                DashboardReactivationRow(
                    cliente_id="cli-9",
                    cliente_codigo=909,
                    cliente_nombre="Cliente frio",
                    isla_nombre="Tenerife",
                    last_contact=None,
                    current_kg=15.0,
                    previous_kg=40.0,
                    delta_kg=-25.0,
                    priority="Alta",
                )
            ],
            island_rows=[
                DashboardIslandRow(isla_nombre="Gran Canaria", pending=2, postponed=1, completed=0, total=3)
            ],
            reactivation_metric_label="Variación kg · 2026-06 vs 2026-07",
            generated_at=datetime(2026, 7, 21, 9, 30, 0),
        )

    def list_all_activities(self):
        return self.load_snapshot().today_items


class _StubCustomerService:
    def list(self, _term: str):
        return []

    def get_agenda_activity(self, _agenda_id: str):
        return None

    def upsert_agenda_activity(self, _agenda_id: str, _payload: dict):
        return None

    def delete_agenda_activity(self, _agenda_id: str):
        return True


def test_dashboard_page_renders_named_controls_and_snapshot() -> None:
    _application()
    page = DashboardPage(customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService())

    assert page.objectName() == "dashboardPageRoot"
    assert page.sidebar.objectName() == "dashboardSidebar"
    assert page.new_activity_btn.objectName() == "dashboardNewActivityButton"
    assert page.full_agenda_btn.objectName() == "dashboardFullAgendaButton"
    assert page.kpi_labels["pending_today"].text() == "2"
    assert page.kpi_labels["overdue"].text() == "1"
    assert page.kpi_labels["completed_today"].text() == "3"
    assert page.kpi_labels["customers_without_follow_up"].text() == "4"
    assert page.reactivation_table.rowCount() == 1
    assert page.reactivation_table.item(0, 3).text() == "-25,00 kg"
    assert page.island_table.rowCount() == 1
    assert "Variación kg" in page.footer_label.text()


def test_dashboard_page_uses_static_layout_without_scrollbar() -> None:
    _application()
    page = DashboardPage(customer_service=_StubCustomerService(), dashboard_service=_StubDashboardService())
    page.resize(1380, 760)
    page.show()
    QApplication.processEvents()

    content = page.findChild(QWidget, "dashboardContent")

    assert content is not None
    assert page.findChildren(QScrollArea) == []
    assert page.sizeHint().height() <= page.height()
    assert content.sizeHint().height() <= page.height()
