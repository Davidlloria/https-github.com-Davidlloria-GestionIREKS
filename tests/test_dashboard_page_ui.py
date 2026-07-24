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
                    pedido_id="ped-1",
                    almacen_id="alm-1",
                    almacen_nombre="Distribuidor Norte",
                    pedido_fecha=date(2026, 7, 20),
                    pedido_numero="P-001",
                    semana=30,
                    ordered_kg=1000.0,
                    received_kg=750.0,
                    pending_kg=250.0,
                    incident_kg=0.0,
                    status="parcial",
                    last_receipt=date(2026, 7, 22),
                )
            ],
            pending_orders=[
                DashboardOrderRow(
                    pedido_id="ped-2",
                    almacen_id="alm-2",
                    almacen_nombre="Cliente Centro",
                    pedido_fecha=date(2026, 7, 18),
                    pedido_numero="P-002",
                    semana=29,
                    ordered_kg=850.0,
                    received_kg=0.0,
                    pending_kg=850.0,
                    incident_kg=0.0,
                    status="pendiente",
                    last_receipt=None,
                )
            ],
            warehouse_rows=[
                DashboardOrdersWarehouseRow(
                    almacen_id="alm-2",
                    almacen_nombre="Cliente Centro",
                    open_orders=3,
                    pending_kg=1250.0,
                    last_receipt=date(2026, 7, 21),
                )
            ],
            state_rows=[
                DashboardOrdersStateRow(status="Pendiente", count=4, kg=2100.0),
                DashboardOrdersStateRow(status="Parcial", count=6, kg=9200.0),
            ],
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
                    cliente_id="cli-31",
                    cliente_codigo="431",
                    cliente_nombre="Panaderia Azul",
                    isla="Gran Canaria",
                    cliente_tipo="Indirecto",
                    kg_prev=1500.0,
                    kg_curr=950.0,
                    delta_kg=-550.0,
                    delta_pct=-36.67,
                )
            ],
            island_rows=[
                DashboardSalesIslandRow(
                    isla="Gran Canaria",
                    customers=25,
                    kg_prev=6400.0,
                    kg_curr=7100.0,
                    delta_kg=700.0,
                    share_pct=28.98,
                )
            ],
            type_rows=[
                DashboardSalesTypeRow(
                    cliente_tipo="Indirecto",
                    customers=54,
                    kg_curr=18400.0,
                    delta_kg=-950.0,
                    share_pct=75.10,
                )
            ],
            zero_consumption_rows=[
                DashboardSalesCustomerRow(
                    cliente_id="cli-45",
                    cliente_codigo="777",
                    cliente_nombre="Cliente Dormido",
                    isla="Lanzarote",
                    cliente_tipo="Directo",
                    kg_prev=250.0,
                    kg_curr=0.0,
                    delta_kg=-250.0,
                    delta_pct=-100.0,
                )
            ],
            generated_at=datetime(2026, 7, 24, 12, 45, 0),
        )


class _StubWarehouseDashboardService:
    def load_snapshot(self) -> WarehouseDashboardSnapshot:
        return WarehouseDashboardSnapshot(
            year=2026,
            month=7,
            total_stock_kg=8425.0,
            risk_items=3,
            entries_month_kg=2150.0,
            outputs_month_kg=1745.5,
            risk_rows=[
                DashboardWarehouseRiskRow(
                    almacen_id="alm-1",
                    almacen_nombre="Almacén Norte",
                    articulo_id="art-1",
                    referencia="5001",
                    nombre="Mezcla Muffin",
                    lote="L-100",
                    caducidad=date(2026, 7, 28),
                    stock_units=2.0,
                    stock_kg=50.0,
                    state="Caduca pronto",
                )
            ],
            warehouse_rows=[
                DashboardWarehouseStockRow(
                    almacen_id="alm-1",
                    almacen_nombre="Almacén Norte",
                    article_count=18,
                    stock_kg=4200.0,
                )
            ],
            entry_rows=[
                DashboardWarehouseMovementRow(
                    almacen_id="alm-1",
                    almacen_nombre="Almacén Norte",
                    articulo_id="art-1",
                    referencia="5001",
                    nombre="Mezcla Muffin",
                    fecha=date(2026, 7, 22),
                    units=4.0,
                    kg=100.0,
                    document_number="ALB-1",
                )
            ],
            output_rows=[
                DashboardWarehouseMovementRow(
                    almacen_id="alm-2",
                    almacen_nombre="Almacén Sur",
                    articulo_id="art-2",
                    referencia="7002",
                    nombre="Pan rallado",
                    fecha=date(2026, 7, 23),
                    units=3.0,
                    kg=75.5,
                    document_number="SAL-9",
                )
            ],
            low_stock_threshold_units=1.0,
            generated_at=datetime(2026, 7, 24, 11, 0, 0),
        )


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


def test_dashboard_page_switches_to_orders_mode_and_renders_snapshot() -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
        order_dashboard_service=_StubOrderDashboardService(),
    )

    page._set_dashboard_mode("pedidos")

    assert page.title_label.text() == "Pedidos"
    assert page.new_activity_btn.text() == "Ver pedidos"
    assert page.full_agenda_btn.text() == "Actualizar"
    assert page.order_kpi_labels["total_orders"].text() == "12"
    assert page.order_kpi_labels["received_kg"].text() == "15.250,00"
    assert page.order_kpi_labels["pending_kg"].text() == "1.875,50"
    assert page.order_kpi_labels["incident_orders"].text() == "2"
    assert page.orders_recent_table.rowCount() == 1
    assert page.orders_recent_table.item(0, 1).text() == "Distribuidor Norte"
    assert page.orders_pending_table.rowCount() == 1
    assert page.orders_warehouse_table.rowCount() == 1
    assert page.orders_state_table.rowCount() == 2
    assert "Pedidos 2026" in page.footer_label.text()


def test_dashboard_page_switches_to_warehouse_mode_and_renders_snapshot() -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
        order_dashboard_service=_StubOrderDashboardService(),
        warehouse_dashboard_service=_StubWarehouseDashboardService(),
    )

    page._set_dashboard_mode("almacen")

    assert page.title_label.text() == "Almacén"
    assert page.new_activity_btn.text() == "Ver almacén"
    assert page.full_agenda_btn.text() == "Actualizar"
    assert page.warehouse_kpi_labels["total_stock_kg"].text() == "8.425,00"
    assert page.warehouse_kpi_labels["risk_items"].text() == "3"
    assert page.warehouse_kpi_labels["entries_month_kg"].text() == "2.150,00"
    assert page.warehouse_kpi_labels["outputs_month_kg"].text() == "1.745,50"
    assert page.warehouse_risk_table.rowCount() == 1
    assert page.warehouse_risk_table.item(0, 0).text() == "Almacén Norte"
    assert page.warehouse_stock_table.rowCount() == 1
    assert page.warehouse_entries_table.rowCount() == 1
    assert page.warehouse_outputs_table.rowCount() == 1
    assert "umbral bajo stock" in page.footer_label.text()


def test_dashboard_page_switches_to_sales_mode_and_renders_snapshot() -> None:
    _application()
    page = DashboardPage(
        customer_service=_StubCustomerService(),
        dashboard_service=_StubDashboardService(),
        sales_dashboard_service=_StubSalesDashboardService(),
    )

    page._set_dashboard_mode("ventas")

    assert page.title_label.text() == "Ventas"
    assert page.new_activity_btn.text() == "Ver ventas"
    assert page.full_agenda_btn.text() == "Actualizar"
    assert page.sales_kpi_labels["total_kg"].text() == "24.500,00"
    assert page.sales_kpi_labels["delta_kg"].text() == "-1.250,50"
    assert page.sales_kpi_labels["active_customers"].text() == "87"
    assert page.sales_kpi_labels["active_islands"].text() == "5"
    assert page.sales_drops_table.rowCount() == 1
    assert page.sales_drops_table.item(0, 0).text() == "431 · Panaderia Azul"
    assert page.sales_islands_table.rowCount() == 1
    assert page.sales_types_table.rowCount() == 1
    assert page.sales_zero_table.rowCount() == 1
    assert "Ventas 2026 vs 2025" in page.footer_label.text()
