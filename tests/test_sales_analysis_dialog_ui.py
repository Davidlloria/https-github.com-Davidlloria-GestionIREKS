import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.ui.widgets import sales_page as sales_page_module
from app.ui.widgets.sales_page import SALES_PRODUCT_ID_ROLE, SalesAnalysisDialog, SalesPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_sales_analysis_dialog_uses_sales_query_assistant(monkeypatch) -> None:
    _app()
    calls: list[tuple[str, dict[str, object]]] = []

    class _FakeAssistant:
        def __init__(self, sales_service=None) -> None:
            self.sales_service = sales_service

        def answer(self, question: str, defaults: dict[str, object]):
            calls.append((question, defaults))
            return SimpleNamespace(ok=True, text="respuesta final", message="ok")

    class _FakeExportService:
        def default_path(self, *args, **kwargs):
            return "salida.txt"

    monkeypatch.setattr(sales_page_module, "SalesQueryAssistantService", _FakeAssistant)
    monkeypatch.setattr(sales_page_module, "ReportExportService", _FakeExportService)

    dialog = SalesAnalysisDialog(title="Analisis", defaults={"year": 2026}, sales_service=object())
    assert "ChatGPT" not in dialog.findChildren(sales_page_module.QLabel)[0].text()
    dialog.question_edit.setPlainText("dame resumen")
    dialog._consult()

    assert calls == [("dame resumen", {})]
    assert dialog.response_edit.toPlainText() == "respuesta final"
    dialog.close()


def test_build_sales_analysis_defaults_collects_visible_filters() -> None:
    page = SalesPage.__new__(SalesPage)
    page._selected_sales_row = lambda: ("art-1", "COD-1", "Producto 1")
    page._current_client_id = lambda: "cli-1"
    page._current_client_name = lambda: "Cliente Uno"
    page._current_product_text = lambda: "muffin"
    page._current_manufacturer_id = lambda: "fab-1"
    page._current_family_id = lambda: "fam-1"
    page._current_subfamily_id = lambda: "sub-1"
    page._current_year = lambda: 2026
    page._current_month = lambda: 7
    page.acumulado_check = SimpleNamespace(isChecked=lambda: True)

    defaults = SalesPage._build_sales_analysis_defaults(page)

    assert defaults == {
        "year": 2026,
        "month": 7,
        "acumulado": True,
        "cliente_id": "cli-1",
        "cliente_texto": "Cliente Uno",
        "articulo_id": "art-1",
        "producto_texto": "muffin",
        "fabricante_id": "fab-1",
        "familia_id": "fam-1",
        "subfamilia_id": "sub-1",
        "limit": 200,
    }


def test_build_sales_analysis_defaults_clears_empty_global_filters() -> None:
    page = SalesPage.__new__(SalesPage)
    page._selected_sales_row = lambda: None
    page._current_client_id = lambda: ""
    page._current_client_name = lambda: "Todos los clientes"
    page._current_product_text = lambda: ""
    page._current_manufacturer_id = lambda: ""
    page._current_family_id = lambda: ""
    page._current_subfamily_id = lambda: ""
    page._current_year = lambda: 2026
    page._current_month = lambda: 0
    page.acumulado_check = SimpleNamespace(isChecked=lambda: False)

    defaults = SalesPage._build_sales_analysis_defaults(page)

    assert defaults["cliente_texto"] == ""
    assert defaults["producto_texto"] == ""
    assert defaults["articulo_id"] == ""
    assert defaults["acumulado"] is False


def test_sales_product_tables_offer_consumers_context_menu(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(SalesPage, "reload", lambda self: None)
    monkeypatch.setattr(SalesPage, "reload_igsa", lambda self: None)
    monkeypatch.setattr(SalesPage, "reload_clientes", lambda self: None)
    page = SalesPage()

    for table in (page.sales_table, page.sales_table_igsa, page.sales_table_clientes):
        assert table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    def igsa_row(product_id: str, code: str, name: str):
        return SimpleNamespace(
            articulo_id=product_id,
            codigo=code,
            nombre=name,
            kilos_prev=1.0,
            sc_prev=0.0,
            ventas_prev=2.0,
            kilos_curr=3.0,
            sc_curr=0.0,
            ventas_curr=4.0,
            delta_kg=2.0,
            delta_kg_pct=200.0,
            delta_ventas=2.0,
            delta_ventas_pct=100.0,
        )

    page._fill_sales_igsa(
        [
            igsa_row("art-igsa-2", "IG-002", "Producto IGSA 2"),
            igsa_row("art-igsa-1", "IG-001", "Producto IGSA"),
        ],
        2026,
    )
    code_item = page.sales_table_igsa.findItems("IG-001", Qt.MatchFlag.MatchExactly)[0]
    assert code_item.data(SALES_PRODUCT_ID_ROLE) == "art-igsa-1"
    captured: list[tuple[int, str, str, str]] = []

    class _Menu:
        def __init__(self, _parent) -> None:
            self.action = None

        def addAction(self, text: str):
            assert text == "Ver clientes que compran este producto"
            self.action = object()
            return self.action

        def exec(self, _pos):
            return self.action

    monkeypatch.setattr(sales_page_module, "QMenu", _Menu)
    monkeypatch.setattr(
        page,
        "_show_product_consumers_dialog",
        lambda year, product_id, code, name: captured.append((year, product_id, code, name)),
    )

    page._open_sales_product_consumers_context_menu(
        page.sales_table_igsa,
        2026,
        page.sales_table_igsa.visualItemRect(code_item).center(),
    )

    assert page.sales_table_igsa.selectionModel().selectedRows()[0].row() == code_item.row()
    assert captured == [(2026, "art-igsa-1", "IG-001", "Producto IGSA")]
    page.close()
    page.deleteLater()
    QApplication.processEvents()
