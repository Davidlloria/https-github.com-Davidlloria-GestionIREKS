from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QSplitter

from app.ui.widgets.orders_page import OrdersPage


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_main_orders_ribbon_is_above_splitter_and_uses_icons(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    main_layout = page.layout()
    ribbon = main_layout.itemAt(0).widget()
    splitter = main_layout.itemAt(1).widget()

    assert isinstance(ribbon, QFrame)
    assert ribbon.objectName() == "topRibbon"
    assert ribbon.property("pageType") == "contacts"
    assert isinstance(splitter, QSplitter)
    assert splitter.frameShape() == QFrame.Shape.NoFrame
    assert not splitter.autoFillBackground()
    assert splitter.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    right_panel = splitter.widget(1)
    right_layout = right_panel.layout()
    right_splitter = right_layout.itemAt(0).widget()
    assert right_panel.property("ordersRegion") == "rightPanel"
    assert "#0000FF" in right_panel.styleSheet()
    assert isinstance(right_splitter, QSplitter)
    assert right_splitter.property("ordersRegion") == "rightSplitter"
    assert "#008000" in right_splitter.styleSheet()
    detail_panel = right_splitter.widget(0)
    assert detail_panel.objectName() == "detailPanel"
    assert "#FCFDFF" in detail_panel.styleSheet()
    assert [button.text() for button in ribbon.findChildren(QPushButton)] == [
        "Nuevo",
        "Editar",
        "Eliminar",
        "Exportar",
        "Enviar Outlook",
        "Imprimir",
        "Ayuda",
    ]
    assert all(not button.icon().isNull() for button in ribbon.findChildren(QPushButton))
    assert all(button.iconSize() == QSize(14, 14) for button in ribbon.findChildren(QPushButton))

    page.close()
    page.deleteLater()
    QApplication.processEvents()
