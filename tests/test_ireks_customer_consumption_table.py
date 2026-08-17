from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from app.ui.widgets.ingredients_page import _SortableNumberItem


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_customer_consumption_numeric_cells_sort_by_value() -> None:
    _application()
    table = QTableWidget(2, 1)
    table.setItem(0, 0, _SortableNumberItem("12.00", 12.0))
    table.setItem(1, 0, _SortableNumberItem("2.00", 2.0))

    table.sortItems(0, Qt.SortOrder.AscendingOrder)

    assert table.item(0, 0).text() == "2.00"
    assert table.item(1, 0).text() == "12.00"
