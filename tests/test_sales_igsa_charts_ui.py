import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QPushButton
from app.ui.widgets import sales_page as module


def test_chart_tooltip_stops_on_leave_hide_and_hidden_refresh(monkeypatch):
    from PySide6.QtCore import QEvent, QPoint
    from PySide6.QtGui import QHideEvent
    app = QApplication.instance() or QApplication([])
    chart = module.MonthlySalesChartWidget()
    hidden = []
    monkeypatch.setattr(module.QToolTip, "hideText", lambda: hidden.append(True))
    for action in (
        lambda: chart.leaveEvent(QEvent(QEvent.Type.Leave)),
        lambda: chart.hideEvent(QHideEvent()),
        chart._refresh_hover_tooltip,
    ):
        chart._active_bar_key = (1, "curr")
        chart._tooltip_text = "Ventas"
        chart._tooltip_global_pos = QPoint(10, 10)
        chart._hover_refresh_timer.start()
        action()
        assert not chart._hover_refresh_timer.isActive()
        assert chart._active_bar_key is None
        assert chart._tooltip_text == ""
    assert len(hidden) == 3


def test_sales_tab_change_dismisses_tooltip(monkeypatch):
    app = QApplication.instance() or QApplication([])
    for method in ("reload", "reload_igsa", "reload_clientes"):
        monkeypatch.setattr(module.SalesPage, method, lambda self: None)
    page = module.SalesPage()
    hidden = []
    monkeypatch.setattr(module.QToolTip, "hideText", lambda: hidden.append(True))
    page.sales_tabs.setCurrentIndex(1)
    assert hidden
    page.close()


def test_chart_visible_modes_switch_same_series():
    app = QApplication.instance() or QApplication([])
    dialog = module.MonthlySalesDialog(
        title="Ventas IGSA · 2025 / 2026", subtitle="Año completo",
        points=[module.SalesMonthlyComparisonPoint(month=m, kilos_prev=m, kilos_curr=m * 2)
                for m in range(1, 13)], explicit_modes=True,
    )
    chart = dialog.findChild(module.MonthlySalesChartWidget)
    buttons = {b.text(): b for b in dialog.mode_buttons.buttons()}
    assert chart.chart_mode() == "bar"
    buttons["Líneas"].click()
    assert chart.chart_mode() == "line"
    assert not buttons["Barras"].isChecked()
    buttons["Barras"].click()
    assert chart.chart_mode() == "bar"
    dialog.close()


def test_product_and_total_forward_selection_and_filters(monkeypatch):
    app = QApplication.instance() or QApplication([])
    calls, dialogs = [], []
    page = module.SalesPage.__new__(module.SalesPage)
    page._current_year_igsa = lambda: 2026
    page._current_product_text_igsa = lambda: "pan"
    page._current_manufacturer_id_igsa = lambda: "fab-1"
    page._current_family_id_igsa = lambda: ""
    page._current_subfamily_id_igsa = lambda: ""
    for attr in ("manufacturer_filter_igsa", "family_filter_igsa", "subfamily_filter_igsa"):
        setattr(page, attr, SimpleNamespace(currentText=lambda: "Fabricante"))
    page.sales_summary_service = SimpleNamespace(
        listar_ventas_mensuales_igsa_comparativa=lambda **kw: calls.append(kw) or [])
    page.sales_table_igsa = QTableWidget(1, 2)
    item = QTableWidgetItem("D123")
    item.setData(module.SALES_PRODUCT_ID_ROLE, "art-1")
    page.sales_table_igsa.setItem(0, 0, item)
    page.sales_table_igsa.setItem(0, 1, QTableWidgetItem("Pan"))
    page.sales_chart_btn_igsa = QPushButton()
    page.sales_total_chart_btn_igsa = QPushButton()
    monkeypatch.setattr(module, "MonthlySalesDialog", lambda **kw:
                        dialogs.append(kw) or SimpleNamespace(exec=lambda: None))
    page._update_igsa_chart_buttons()
    assert not page.sales_chart_btn_igsa.isEnabled()
    page._open_igsa_monthly_chart(product=True)
    assert calls == []
    page.sales_table_igsa.selectRow(0)
    page._update_igsa_chart_buttons()
    assert page.sales_chart_btn_igsa.isEnabled()
    page._open_igsa_monthly_chart(product=True)
    page._open_igsa_monthly_chart(product=False)
    assert calls[0] == dict(year=2026, articulo_id="art-1", codigo="D123",
                           producto_texto="pan", fabricante_id="fab-1", familia_id="", subfamilia_id="")
    assert calls[1] == {**calls[0], "articulo_id": "", "codigo": ""}
    assert "sin filtro de mes/acumulado" in dialogs[0]["subtitle"]
    assert dialogs[1]["explicit_modes"] is True
