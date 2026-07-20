from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView

from app.models import AlmacenMovimiento, IngredienteIreks
from app.services.warehouse_movement_service import WarehouseMovementService
from app.ui.widgets.warehouse_page import MovimientosTab, SortableTableWidgetItem


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_entries_filters_columns_date_sort_and_fixed_totals(monkeypatch) -> None:
    app = _application()
    current_year = date.today().year
    movements = [
        AlmacenMovimiento(
            id=1,
            almacen_id="warehouse",
            articulo_id="product",
            cantidad=3,
            fecha_pedido=date(current_year, 1, 20),
            articulo_lote="L-1",
            articulo_caducidad=date(current_year + 1, 1, 31),
            pedido_albaran_numero="ALB-1",
        ),
        AlmacenMovimiento(
            id=2,
            almacen_id="warehouse",
            articulo_id="product",
            cantidad=2,
            fecha_pedido=date(current_year, 3, 5),
            articulo_lote="L-2",
            articulo_caducidad=date(current_year + 1, 3, 31),
            pedido_albaran_numero="ALB-2",
        ),
        AlmacenMovimiento(
            id=3,
            almacen_id="warehouse",
            articulo_id="product",
            cantidad=7,
            fecha_pedido=date(current_year - 1, 2, 1),
        ),
    ]
    product = IngredienteIreks(
        articulo_id="product",
        articulo_referencia_corta="REF",
        articulo_descripcion="Producto",
        articulo_envase_peso_total=25,
    )
    monkeypatch.setattr(
        WarehouseMovementService,
        "movement_payload",
        lambda self, **kwargs: (movements, [product], [], [], []),
    )

    tab = MovimientosTab("in")
    app.processEvents()

    assert tab.year_filter.currentData() == str(current_year)
    assert tab.month_from_filter.currentData() == "1"
    assert tab.month_to_filter.currentData() == "12"
    assert [tab.table.horizontalHeaderItem(i).text() for i in range(8)] == [
        "Fecha",
        "Ref.",
        "Nombre",
        "Uds",
        "Kg",
        "Lote",
        "Caduca",
        "Albarán",
    ]
    header = tab.table.horizontalHeader()
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(4) == QHeaderView.ResizeMode.Fixed
    assert tab.table.columnWidth(4) == 76
    assert tab.table.rowCount() == 2
    assert {tab.table.item(row, 6).text() for row in range(2)} == {
        f"31/01/{current_year + 1}",
        f"31/03/{current_year + 1}",
    }
    assert {tab.table.item(row, 7).text() for row in range(2)} == {"ALB-1", "ALB-2"}
    assert isinstance(tab.table.item(0, 0), SortableTableWidgetItem)

    tab.table.sortItems(0, Qt.SortOrder.AscendingOrder)
    assert [tab.table.item(row, 0).text() for row in range(2)] == [
        f"20/01/{current_year}",
        f"05/03/{current_year}",
    ]
    assert tab.totals_table.item(0, 0).text() == "TOTALES"
    assert tab.totals_table.item(0, 3).text() == "5.00"
    assert tab.totals_table.item(0, 4).text() == "125.00 kg"
    assert tab.layout().itemAt(tab.layout().count() - 1).widget() is tab.totals_table

    tab.table.setColumnWidth(1, 123)
    app.processEvents()
    assert tab.totals_table.columnWidth(1) == 123

    tab.month_from_filter.setCurrentIndex(tab.month_from_filter.findData("2"))
    app.processEvents()
    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 7).text() == "ALB-2"
    assert tab.totals_table.item(0, 3).text() == "2.00"
    assert tab.totals_table.item(0, 4).text() == "50.00 kg"

    tab.deleteLater()
