import csv
import os
from io import StringIO

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableWidgetItem

from app.ui.widgets.ingredients_page import IngredientsIreksPage


def test_tariff_copy_ctrl_selection_shortcut_and_context_action(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(IngredientsIreksPage, "reload", lambda self: None)
    page = IngredientsIreksPage()
    table = page.tarifa_table
    # Display the real table independently from its normally inactive tab.
    table.setParent(None)
    try:
        table.setRowCount(3)
        expected = []
        for row in range(3):
            values = [str(2024 + row), "90,95", "3,64", "5,00 %", "20,00 %", "72,76", "100,00", "4,00", "2,00 %", "27,24 %"]
            expected.append(values)
            for col, text in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(text))
        table.resize(1000, 240)
        table.show()
        table.activateWindow()
        app.processEvents()
        QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=table.visualItemRect(table.item(0, 0)).center())
        QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier,
                         table.visualItemRect(table.item(2, 0)).center())
        assert len(table.selectionModel().selectedRows()) == 2
        assert page.copy_tarifa_action.isEnabled()
        table.setFocus()
        app.processEvents()
        QApplication.clipboard().setText("before")
        QTest.keyClick(table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert list(csv.reader(StringIO(QApplication.clipboard().text()), delimiter="\t")) == [expected[0], expected[2]]
        assert page.copy_tarifa_action in table.actions()
        assert table.contextMenuPolicy() == Qt.ContextMenuPolicy.ActionsContextMenu
        QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=table.visualItemRect(table.item(1, 0)).center())
        page.copy_tarifa_action.trigger()
        assert list(csv.reader(StringIO(QApplication.clipboard().text()), delimiter="\t")) == [expected[1]]
        table.clearSelection()
        assert not page.copy_tarifa_action.isEnabled()
        before = QApplication.clipboard().text()
        page._copy_tarifa_rows()
        assert QApplication.clipboard().text() == before
        assert table.item(0, 1).text() == "90,95"
    finally:
        table.close()
        table.deleteLater()
        page.close()
