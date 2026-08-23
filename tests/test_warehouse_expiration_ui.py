from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from app.models import AlmacenMovimiento, IngredienteIreks
from app.services.warehouse_movement_service import WarehouseMovementService
from app.ui.widgets.warehouse_page import CaducidadTab, SortableTableWidgetItem


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_expiration_visual_dates_colors_metrics_and_typed_sorting(monkeypatch) -> None:
    app = _application()
    today = date.today()
    movements = [
        AlmacenMovimiento(
            id=1,
            almacen_id="warehouse",
            articulo_id="expired-product",
            pedido_numero="10",
            pedido_albaran_numero="ALB-10",
            cantidad=10,
            fecha_pedido=today - timedelta(days=2),
            articulo_lote="900",
            articulo_caducidad=today - timedelta(days=1),
        ),
        AlmacenMovimiento(
            id=2,
            almacen_id="warehouse",
            articulo_id="soon-product",
            pedido_numero="2",
            pedido_albaran_numero="ALB-2",
            cantidad=2,
            fecha_pedido=today - timedelta(days=200),
            articulo_lote="100",
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
    monkeypatch.setattr(
        WarehouseMovementService,
        "expiration_payload",
        lambda self, almacen_id: (movements, products),
    )

    tab = CaducidadTab()
    tab.resize(1500, 800)
    tab.show()
    app.processEvents()

    filter_panel = tab.findChild(QFrame, "expirationFilterPanel")
    results_panel = tab.findChild(QFrame, "expirationResultsPanel")
    assert filter_panel is not None
    assert results_panel is not None
    assert tab.date_from.minimumWidth() == 138
    assert tab.date_to.minimumWidth() == 138
    assert tab.date_from.width() >= 138
    assert tab.date_to.width() >= 138
    assert tab.findChild(QPushButton, "expirationResetButton").text() == "Restablecer"
    assert not tab.findChild(QLabel, "expirationFilterIcon").pixmap().isNull()
    assert not tab.findChild(QLabel, "expirationResultsIcon").pixmap().isNull()
    icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
    for icon_name in ("filtro.svg", "calendar-clock.svg", "eraser.svg"):
        assert ElementTree.parse(icon_dir / icon_name).getroot().tag.endswith("svg")

    assert tab.table.isSortingEnabled()
    assert tab.table.rowCount() == 2
    assert isinstance(tab.table.item(0, 8), SortableTableWidgetItem)
    assert tab.expired_summary.text() == "1 caducado"
    assert tab.soon_summary.text() == "1 próximo"
    assert tab.expiration_kg_summary.text() == "70 kg"

    expired_row = next(row for row in range(2) if tab.table.item(row, 3).text() == "REF-OLD")
    soon_row = next(row for row in range(2) if tab.table.item(row, 3).text() == "REF-SOON")
    assert tab.table.item(expired_row, 0).background().color().name().upper() == "#FDECEC"
    assert tab.table.item(soon_row, 0).background().color().name().upper() == "#FFF4D6"

    tab.table.sortItems(5, Qt.SortOrder.AscendingOrder)
    assert [tab.table.item(row, 3).text() for row in range(2)] == ["REF-SOON", "REF-OLD"]
    tab.table.sortItems(0, Qt.SortOrder.AscendingOrder)
    assert [tab.table.item(row, 0).text() for row in range(2)] == ["2", "10"]
    tab.table.sortItems(2, Qt.SortOrder.AscendingOrder)
    assert [tab.table.item(row, 3).text() for row in range(2)] == ["REF-SOON", "REF-OLD"]
    tab.table.sortItems(8, Qt.SortOrder.AscendingOrder)
    assert [tab.table.item(row, 3).text() for row in range(2)] == ["REF-OLD", "REF-SOON"]

    tab.mode_combo.setCurrentIndex(tab.mode_combo.findData("expired"))
    app.processEvents()
    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 3).text() == "REF-OLD"
    assert tab.expired_summary.text() == "1 caducado"
    assert tab.soon_summary.text() == "0 próximos"

    tab.close()
    tab.deleteLater()
