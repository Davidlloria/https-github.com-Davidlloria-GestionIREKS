from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

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
    _application()
    monkeypatch.setattr(main_window_module, "DashboardPage", lambda: _stub_page("dashboard"))
    monkeypatch.setattr(main_window_module.MainWindow, "_build_customers_page", lambda self: _stub_page("customers"))
    monkeypatch.setattr(main_window_module, "ContactsPage", lambda: _stub_page("contacts"))
    monkeypatch.setattr(main_window_module, "CoursesPage", lambda: _stub_page("courses"))
    monkeypatch.setattr(main_window_module, "DistributorsPage", lambda: _stub_page("distributors"))
    monkeypatch.setattr(main_window_module, "DocumentLibraryPage", lambda: _stub_page("documents"))
    monkeypatch.setattr(main_window_module, "IngredientsIreksPage", lambda: _stub_page("ireks"))
    monkeypatch.setattr(main_window_module, "IngredientsStdPage", lambda: _stub_page("std"))
    monkeypatch.setattr(main_window_module, "OrdersPage", lambda: _stub_page("orders"))
    monkeypatch.setattr(main_window_module, "PlaceholderPage", lambda *_args, **_kwargs: _stub_page("placeholder"))
    monkeypatch.setattr(main_window_module, "RecipesPage", lambda: _stub_page("recipes"))
    monkeypatch.setattr(main_window_module, "SalesPage", lambda: _stub_page("sales"))
    monkeypatch.setattr(main_window_module, "SettingsPage", lambda: _stub_page("settings"))
    monkeypatch.setattr(main_window_module, "TechniciansPage", lambda: _stub_page("technicians"))
    monkeypatch.setattr(main_window_module, "WarehousePage", lambda: _stub_page("warehouse"))

    window = main_window_module.MainWindow()

    assert window.page_names[0] == "Inicio"
    assert window.pages.currentIndex() == 0
    assert window.pages.widget(0).objectName() == "dashboard"
    assert window.ribbon_buttons.button(0).text() == "Inicio"
    documents_index = window.page_names.index("Documentos")
    assert window.page_names[documents_index - 1] == "Formulas"
    assert window.pages.widget(documents_index).objectName() == "documents"
    assert window.ribbon_buttons.button(documents_index).text() == "Documentos"

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
    window._local_ai_status_timer.stop()
