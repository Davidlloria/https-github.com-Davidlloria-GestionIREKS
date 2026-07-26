from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.widgets.orders_page import OrdersPage


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_pedido_tab_uses_split_order_and_received_columns(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    headers = [page.pedido_items_table.horizontalHeaderItem(i).text() for i in range(page.pedido_items_table.columnCount())]

    assert headers == ["Cod.", "Nombre", "Pedido", "Kg", "Recib.", "Kg", "Δ"]
    assert page.pedido_items_totals_table.columnCount() == 7
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_pedido_delta_header_and_zero_value_behavior(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    assert page.pedido_items_table.horizontalHeaderItem(6).text() == "Δ"

    page.close()
    page.deleteLater()
    QApplication.processEvents()



def test_pendientes_tab_uses_accumulated_pending_columns(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    headers = [page.pendientes_table.horizontalHeaderItem(i).text() for i in range(page.pendientes_table.columnCount())]

    assert headers == ["Cod.", "Nombre", "Pendiente", "Pedido"]
    assert page.pendientes_table.isSortingEnabled()
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_new_order_uses_typed_almacen_filter_text(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    page.almacen_filter.addItem("Todos", "")
    page.almacen_filter.addItem("Distribuidor Norte", "dist-norte")
    page.almacen_filter.addItem("Cliente Sur", "cli-sur")
    page.almacen_filter.setCurrentIndex(0)
    page.almacen_filter.lineEdit().setText("norte")

    assert page._selected_almacen_id() == "dist-norte"

    page.close()
    page.deleteLater()
    QApplication.processEvents()



def test_pedido_tab_uses_split_order_and_received_columns(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    headers = [page.pedido_items_table.horizontalHeaderItem(i).text() for i in range(page.pedido_items_table.columnCount())]

    assert headers == ["Cod.", "Nombre", "Pedido", "Kg", "Recib.", "Kg", "?"]
    assert page.pedido_items_totals_table.columnCount() == 7
    page.close()
    page.deleteLater()
    QApplication.processEvents()
