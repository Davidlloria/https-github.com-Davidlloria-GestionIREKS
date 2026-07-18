from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QSplitter

from app.ui.widgets.orders_page import OrdersPage


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_main_orders_ribbon_is_above_splitter_and_uses_customer_standard(monkeypatch) -> None:
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
    assert [button.text() for button in ribbon.findChildren(QPushButton)] == [
        "Nuevo pedido",
        "Editar",
        "Eliminar",
        "Exportar",
        "Enviar Outlook",
        "Imprimir",
    ]
    assert [button.property("btnRole") for button in ribbon.findChildren(QPushButton)] == [
        "success",
        "warning",
        "danger",
        "secondary",
        "secondary",
        "secondary",
    ]
    page.close()
    page.deleteLater()
    QApplication.processEvents()
