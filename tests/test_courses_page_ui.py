from __future__ import annotations

import os
from datetime import date
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from app.ui.widgets.courses_page import CoursesPage


def test_courses_reload_sorts_dates_chronologically_and_preserves_row_identity() -> None:
    app = QApplication.instance() or QApplication([])
    table = QTableWidget(0, 2)
    dates = [date(2026, 1, 2), date(2025, 12, 31), date(2026, 2, 1), date(2026, 1, 15)]
    rows = [SimpleNamespace(curso_fecha=value, curso_id=value.isoformat(),
                            curso_nombre=f"Curso {value.isoformat()}") for value in dates]
    empty_filter = SimpleNamespace(currentData=lambda: None)
    page = SimpleNamespace(
        year_filter=empty_filter, month_start_filter=empty_filter,
        month_end_filter=empty_filter, search_input=SimpleNamespace(text=lambda: ""),
        service=SimpleNamespace(list_courses=lambda **kwargs: rows), table=table,
        _show_selected_details=lambda: None,
    )
    try:
        for order, reverse in ((Qt.SortOrder.AscendingOrder, False),
                               (Qt.SortOrder.DescendingOrder, True)):
            table.sortItems(0, order)
            CoursesPage.reload(page)
            for index, value in enumerate(sorted(dates, reverse=reverse)):
                cell = table.item(index, 0)
                assert cell.text() == value.strftime("%d/%m/%Y")
                assert cell.data(Qt.ItemDataRole.UserRole) == value.isoformat()
                assert table.item(index, 1).text() == f"Curso {value.isoformat()}"
    finally:
        table.close()
        table.deleteLater()
        app.processEvents()
