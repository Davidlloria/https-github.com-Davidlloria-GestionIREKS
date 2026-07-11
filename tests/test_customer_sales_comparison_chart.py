import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QLabel

from app.ui.widgets import customers_page
from app.ui.widgets.customers_page import CustomerSalesComparisonChartDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _row(*, code: str, name: str, prev: float, curr: float) -> SimpleNamespace:
    return SimpleNamespace(codigo=code, nombre=name, kg_prev=prev, kg_curr=curr)


def test_customer_sales_chart_uses_kg_series_and_year_labels() -> None:
    app = _app()
    rows = [
        _row(code="ART-1", name="Producto uno", prev=12.5, curr=18.0),
        _row(code="ART-2", name="Producto dos", prev=7.0, curr=5.5),
    ]

    dialog = CustomerSalesComparisonChartDialog(rows=rows, year=2026, customer_name="Cliente Uno")
    app.processEvents()

    labels = [label.text() for label in dialog.findChildren(QLabel)]
    assert "Comparativa de ventas en kg · Cliente Uno" in labels
    assert "Productos · 2025 vs 2026" in labels
    if customers_page.pg is not None:
        assert dialog._plot.getAxis("left").labelText == "Kg"
        assert [region["value"] for region in dialog._hover_regions] == [12.5, 18.0, 7.0, 5.5]

    dialog.close()


def test_customer_sales_chart_keeps_one_pair_of_bars_per_product() -> None:
    _app()
    rows = [_row(code="ART-1", name="Producto uno", prev=3.0, curr=4.0)]

    dialog = CustomerSalesComparisonChartDialog(rows=rows, year=2025, customer_name="Cliente")

    if customers_page.pg is not None:
        assert len(dialog._hover_regions) == 2
        assert {region["index"] for region in dialog._hover_regions} == {0}

    dialog.close()


def test_customer_sales_chart_exposes_product_name_for_each_reference() -> None:
    _app()
    rows = [
        _row(code=f"ART-{index}", name=f"Producto {index}", prev=float(index), curr=float(index + 1))
        for index in range(15)
    ]

    dialog = CustomerSalesComparisonChartDialog(rows=rows, year=2026, customer_name="Cliente")

    assert dialog._product_index_at_x(0.0) == 0
    assert dialog._product_index_at_x(12.2) == 12
    assert dialog._product_index_at_x(14.0) == 14
    assert dialog._product_index_at_x(14.8) is None

    if customers_page.pg is not None:
        x_min, x_max = dialog._plot.viewRange()[0]
        assert x_min <= -0.7
        assert x_max >= 14.7

    dialog.close()


def test_customer_sales_chart_shows_tooltips_for_bar_and_reference(monkeypatch) -> None:
    app = _app()
    rows = [_row(code="ART-1", name="Producto completo", prev=3.0, curr=4.0)]
    dialog = CustomerSalesComparisonChartDialog(rows=rows, year=2026, customer_name="Cliente")
    dialog.show()
    app.processEvents()

    if customers_page.pg is not None:
        shown_texts = []
        monkeypatch.setattr(customers_page.QToolTip, "showText", lambda _pos, text, _widget: shown_texts.append(text))
        view_box = dialog._plot.getPlotItem().vb

        dialog._show_tooltip(view_box.mapViewToScene(QPointF(-0.2, 1.0)))
        dialog._show_tooltip(view_box.mapViewToScene(QPointF(0.0, -1.0)))

        assert shown_texts[0] == "Producto completo\n2025: 3,00 kg\n2026: 4,00 kg"
        assert shown_texts[1] == "Producto completo"

    dialog.close()
