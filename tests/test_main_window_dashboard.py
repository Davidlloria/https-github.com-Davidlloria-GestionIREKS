from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Signal

import app.ui.main_window as main_window_module


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _stub_page(name: str) -> QWidget:
    widget = QWidget()
    widget.setObjectName(name)
    return widget


def test_main_window_starts_on_inicio_page(monkeypatch) -> None:
    application = _application()
    application.setStyleSheet(
        (Path(__file__).resolve().parents[1] / "assets" / "styles.qss").read_text(encoding="utf-8")
    )
    def _dashboard_stub(*, settings_page=None):
        widget = _stub_page("dashboard")
        widget.settings_page = settings_page
        return widget

    created = []
    refreshed = []
    focused = []

    class DeferredPage(QWidget):
        product_requested = Signal(str, str)

        def __init__(self, name):
            super().__init__()
            self.setObjectName(name)
            created.append(name)

        def reload(self):
            refreshed.append(self.objectName())

        def focus_article(self, identity, section):
            focused.append((identity, section))

    monkeypatch.setattr(main_window_module, "DashboardPage", _dashboard_stub)
    monkeypatch.setattr(main_window_module.MainWindow, "_build_customers_page", lambda self: _stub_page("customers"))
    monkeypatch.setattr(main_window_module, "ContactsPage", lambda: _stub_page("contacts"))
    monkeypatch.setattr(main_window_module, "CoursesPage", lambda: _stub_page("courses"))
    monkeypatch.setattr(main_window_module, "DistributorsPage", lambda: _stub_page("distributors"))
    monkeypatch.setattr(main_window_module, "DocumentLibraryPage", lambda: _stub_page("documents"))
    monkeypatch.setattr(main_window_module, "IngredientsIreksPage", lambda: DeferredPage("ireks"))
    monkeypatch.setattr(main_window_module, "IngredientsStdPage", lambda: DeferredPage("std"))
    monkeypatch.setattr(main_window_module, "OrdersPage", lambda: _stub_page("orders"))
    monkeypatch.setattr(main_window_module, "PlaceholderPage", lambda *_args, **_kwargs: _stub_page("placeholder"))
    monkeypatch.setattr(main_window_module, "RecipesPage", lambda: _stub_page("recipes"))
    monkeypatch.setattr(main_window_module, "SalesPage", lambda: _stub_page("sales"))
    monkeypatch.setattr(main_window_module, "SettingsPage", lambda **_kwargs: _stub_page("settings"))
    monkeypatch.setattr(main_window_module, "TechniciansPage", lambda: _stub_page("technicians"))
    monkeypatch.setattr(main_window_module, "WarehousePage", lambda: DeferredPage("warehouse"))

    window = main_window_module.MainWindow()
    assert created == []

    assert window.windowTitle() == "Gestión IREKS"
    assert window.page_names[0] == "Inicio"
    assert window.pages.currentIndex() == 0
    assert window.pages.widget(0).objectName() == "dashboard"
    assert window.dashboard_page.settings_page is window.settings_page
    assert window.settings_page.objectName() == "settings"
    assert "Configuracion" not in window.page_names
    assert window.ribbon_buttons.button(0).text() == "Inicio"
    documents_index = window.page_names.index("Documentos")
    assert window.pages.widget(documents_index).objectName() == "documents"
    assert window.ribbon_buttons.button(documents_index).text() == "Documentos"
    ribbon_buttons = [
        window.ribbon_layout.itemAt(index).widget()
        for index in range(window.ribbon_layout.count())
        if window.ribbon_layout.itemAt(index).widget() is not None
        and window.ribbon_layout.itemAt(index).widget().property("navButton")
    ]
    ribbon_labels = [button.text() for button in ribbon_buttons]
    assert ribbon_labels == [
        "Inicio",
        "Clientes",
        "Contactos",
        "Técnicos",
        "Distribuidores",
        "Colaboradores",
        "Cursos",
        "Fórmulas",
        "Almacén",
        "Productos",
        "Materias primas",
        "Pedidos",
        "Ventas",
        "Documentos",
    ]
    assert all(not button.icon().isNull() for button in ribbon_buttons)
    assert all(button.iconSize().width() == 19 for button in ribbon_buttons)
    separators = window.ribbon.findChildren(QWidget, "mainRibbonSeparator")
    assert len(separators) == 3
    window.resize(2200, 720)
    window.show()
    QApplication.processEvents()
    assert all(
        button.minimumWidth() == button.maximumWidth()
        and button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 30
        for button in ribbon_buttons
    )
    assert ribbon_buttons[-1].geometry().right() <= window.ribbon.contentsRect().right()

    statuses = []
    window.dashboard_page.set_local_ai_status = lambda code, message: statuses.append((code, message))
    lifecycle = SimpleNamespace(status_code="checking", status="Comprobando IA local...")
    window.bind_local_ai_lifecycle(lifecycle)
    assert statuses == [("checking", "Comprobando IA local...")]
    window._sync_local_ai_status()
    assert len(statuses) == 1
    lifecycle.status_code = "ready"
    lifecycle.status = "IA local disponible"
    window._sync_local_ai_status()
    assert statuses[-1] == ("ready", "IA local disponible")

    # The warehouse link must construct Products before focusing the article.
    warehouse_index = window.page_names.index("Almacen")
    products_index = window.page_names.index("Productos IREKS")
    std_index = window.page_names.index("Materias primas")
    page_count = window.pages.count()
    window.ribbon_buttons.button(warehouse_index).click()
    warehouse = window.pages.widget(warehouse_index)
    assert created == ["warehouse"]
    warehouse.product_requested.emit("article-1", "Stock")
    products = window.pages.widget(products_index)
    assert window.pages.currentWidget() is products
    assert focused == [("article-1", "Stock")]
    assert created == ["warehouse", "ireks"]
    window.ribbon_buttons.button(std_index).click()
    std = window.pages.widget(std_index)
    for index, page in ((warehouse_index, warehouse), (products_index, products), (std_index, std)):
        window.ribbon_buttons.button(0).click()
        window.ribbon_buttons.button(index).click()
        assert window.pages.currentWidget() is page
        assert window.ribbon_buttons.checkedId() == index
    assert created == ["warehouse", "ireks", "std"]
    assert refreshed == ["warehouse", "ireks", "std", "warehouse", "ireks", "std"]
    assert window.pages.count() == page_count
    assert window.pages.widget(documents_index).objectName() == "documents"
    assert window.pages.widget(window.page_names.index("Pedidos")).objectName() == "orders"
    window._local_ai_status_timer.stop()
    window.close()
    window.deleteLater()
    QApplication.processEvents()
    application.setStyleSheet("")
