import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.widgets import sales_page as sales_page_module
from app.ui.widgets.sales_page import SalesAnalysisDialog, SalesPage


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
