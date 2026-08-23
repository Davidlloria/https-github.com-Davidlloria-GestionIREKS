from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from app.models import IngredienteIreks
from app.services.monthly_orders_service import AnnualProductOrderRow, MonthlyOrdersService
from app.services.warehouse_movement_service import WarehouseMovementService
from app.ui.widgets.warehouse_page import AnnualMonthlyOrdersTab


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_monthly_orders_visual_filters_svg_metrics_and_no_refresh(monkeypatch) -> None:
    app = _application()
    current_year = date.today().year
    first_months = [3.0] + [0.0] * 11
    second_months = [0.0, 2.0] + [0.0] * 10
    rows = [
        AnnualProductOrderRow(
            articulo_id="product-1",
            referencia="REF-1",
            descripcion="Producto primero",
            monthly_quantities=first_months,
            total_quantity=3.0,
            total_kg=15.0,
            order_count=1,
            last_order_date=date(current_year, 1, 15),
        ),
        AnnualProductOrderRow(
            articulo_id="product-2",
            referencia="REF-2",
            descripcion="Producto segundo",
            monthly_quantities=second_months,
            total_quantity=2.0,
            total_kg=20.0,
            order_count=2,
            last_order_date=date(current_year, 2, 20),
        ),
    ]
    products = [
        IngredienteIreks(
            articulo_id="product-1",
            articulo_referencia_corta="REF-1",
            articulo_descripcion="Producto primero",
            articulo_envase_peso_total=5,
            fabricante_id="manufacturer-1",
            articulo_familia_id="family-1",
            articulo_subfamilia_id="subfamily-1",
        ),
        IngredienteIreks(
            articulo_id="product-2",
            articulo_referencia_corta="REF-2",
            articulo_descripcion="Producto segundo",
            articulo_envase_peso_total=10,
            fabricante_id="manufacturer-2",
            articulo_familia_id="family-2",
            articulo_subfamilia_id="subfamily-2",
        ),
    ]
    monkeypatch.setattr(
        MonthlyOrdersService,
        "available_years_for",
        lambda self, **kwargs: [current_year],
    )
    monkeypatch.setattr(
        MonthlyOrdersService,
        "annual_product_matrix_for",
        lambda self, **kwargs: rows,
    )
    monkeypatch.setattr(
        WarehouseMovementService,
        "movement_payload",
        lambda self, **kwargs: (
            [],
            products,
            [("manufacturer-1", "IREKS"), ("manufacturer-2", "OTRO")],
            [("family-1", "Ingredientes"), ("family-2", "Decoración")],
            [("subfamily-1", "Maltas"), ("subfamily-2", "Cremas")],
        ),
    )

    tab = AnnualMonthlyOrdersTab()
    app.processEvents()

    filter_panel = tab.findChild(QFrame, "monthlyOrdersFilterPanel")
    orders_panel = tab.findChild(QFrame, "monthlyOrdersPanel")
    assert filter_panel is not None
    assert orders_panel is not None
    assert tab.manufacturer_filter.count() == 3
    assert tab.family_filter.count() == 3
    assert tab.subfamily_filter.count() == 3
    assert all(button.text() != "Refrescar" for button in tab.findChildren(QPushButton))
    assert not tab.findChild(QLabel, "monthlyOrdersFilterIcon").pixmap().isNull()
    assert not tab.findChild(QLabel, "monthlyOrdersPanelIcon").pixmap().isNull()
    icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
    for icon_name in ("filtro.svg", "calendar-range.svg"):
        assert ElementTree.parse(icon_dir / icon_name).getroot().tag.endswith("svg")

    assert tab.table.rowCount() == 2
    assert tab.monthly_products_summary.text() == "2 productos"
    assert tab.monthly_units_summary.text() == "5 uds"
    assert tab.monthly_kg_summary.text() == "35 kg"
    assert tab.monthly_totals_table.item(0, 0).text() == "TOTALES"
    assert tab.monthly_totals_table.item(0, 2).text() == "3.00"
    assert tab.monthly_totals_table.item(0, 3).text() == "2.00"
    assert tab.monthly_totals_table.item(0, 14).text() == "5.00"
    assert tab.monthly_totals_table.item(0, 15).text() == "35.00 kg"
    assert tab.monthly_totals_table.item(0, 16).text() == "3"
    assert tab.layout().itemAt(tab.layout().count() - 1).widget() is orders_panel

    tab.manufacturer_filter.setCurrentIndex(tab.manufacturer_filter.findData("manufacturer-1"))
    app.processEvents()
    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 0).text() == "REF-1"
    assert tab.monthly_products_summary.text() == "1 producto"
    assert tab.monthly_units_summary.text() == "3 uds"
    assert tab.monthly_kg_summary.text() == "15 kg"

    tab.manufacturer_filter.setCurrentIndex(0)
    tab.family_filter.setCurrentIndex(tab.family_filter.findData("family-2"))
    app.processEvents()
    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 0).text() == "REF-2"

    tab.deleteLater()
