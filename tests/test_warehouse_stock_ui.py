from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel

from app.models import AlmacenMovimiento, IngredienteIreks
from app.services.warehouse_movement_service import WarehouseMovementService
from app.services.warehouse_settings_service import WarehouseSettingsService
from app.ui.widgets.warehouse_page import StockTab


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_stock_uses_visual_panels_svg_icons_metrics_and_fixed_totals(monkeypatch) -> None:
    app = _application()
    today = date.today()
    movements = [
        AlmacenMovimiento(
            id=1,
            almacen_id="warehouse",
            articulo_id="expired-product",
            cantidad=3,
            fecha_pedido=today - timedelta(days=20),
            articulo_lote="LOT-OLD",
            articulo_caducidad=today - timedelta(days=1),
        ),
        AlmacenMovimiento(
            id=2,
            almacen_id="warehouse",
            articulo_id="soon-product",
            cantidad=2,
            fecha_pedido=today - timedelta(days=10),
            articulo_lote="LOT-SOON",
            articulo_caducidad=today + timedelta(days=10),
        ),
    ]
    products = [
        IngredienteIreks(
            articulo_id="expired-product",
            articulo_referencia_corta="REF-OLD",
            articulo_descripcion="Producto caducado",
            articulo_envase_peso_total=5,
        ),
        IngredienteIreks(
            articulo_id="soon-product",
            articulo_referencia_corta="REF-SOON",
            articulo_descripcion="Producto próximo",
            articulo_envase_peso_total=10,
        ),
    ]
    monkeypatch.setattr(WarehouseSettingsService, "load", lambda self: {"low_stock_threshold_units": 1.0})
    monkeypatch.setattr(WarehouseSettingsService, "save", lambda self, value: None)
    monkeypatch.setattr(
        WarehouseMovementService,
        "movement_payload",
        lambda self, **kwargs: (movements, products, [], [], []),
    )

    tab = StockTab()
    app.processEvents()

    filter_panel = tab.findChild(QFrame, "stockFilterPanel")
    stock_panel = tab.findChild(QFrame, "stockMovementsPanel")
    assert filter_panel is not None
    assert stock_panel is not None
    assert tab.table.objectName() == "stockTable"
    assert not tab.findChild(QLabel, "stockFilterIcon").pixmap().isNull()
    assert not tab.findChild(QLabel, "stockPanelIcon").pixmap().isNull()
    icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
    for icon_name in ("filtro.svg", "boxes.svg"):
        assert ElementTree.parse(icon_dir / icon_name).getroot().tag.endswith("svg")
    assert tab.table.rowCount() == 2
    assert tab.stock_lots_summary.text() == "2 lotes"
    assert tab.stock_units_summary.text() == "5 uds"
    assert tab.stock_kg_summary.text() == "35 kg"
    assert tab.stock_risks_summary.text() == "2 riesgos"
    assert tab.stock_totals_table.item(0, 0).text() == "TOTALES"
    assert tab.stock_totals_table.item(0, 5).text() == "5,00"
    assert tab.stock_totals_table.item(0, 6).text() == "35,00 kg"
    assert tab.layout().itemAt(tab.layout().count() - 1).widget() is stock_panel

    tab.risk_filter.setCurrentIndex(tab.risk_filter.findData("soon"))
    app.processEvents()
    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 8).text() == "Caduca pronto"
    assert tab.stock_lots_summary.text() == "1 lote"
    assert tab.stock_units_summary.text() == "2 uds"
    assert tab.stock_kg_summary.text() == "20 kg"
    assert tab.stock_risks_summary.text() == "1 riesgo"
    assert tab.stock_totals_table.item(0, 5).text() == "2,00"
    assert tab.stock_totals_table.item(0, 6).text() == "20,00 kg"

    tab.deleteLater()
