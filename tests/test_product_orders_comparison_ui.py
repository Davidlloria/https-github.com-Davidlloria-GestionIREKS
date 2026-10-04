from datetime import date
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.ui.widgets.ingredients_page import IngredientsIreksPage


def test_orders_comparison_keeps_detail_and_aligns_twelve_months(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(IngredientsIreksPage, 'reload', lambda self: None)
    page = IngredientsIreksPage()
    calls = []
    def monthly(**kwargs):
        calls.append(kwargs)
        return [SimpleNamespace(year=2024, month=1, quantity=12.5),
                SimpleNamespace(year=2024, month=12, quantity=9),
                SimpleNamespace(year=2023, month=2, quantity=100)] if kwargs['articulo_id'] == 'p' else []
    monkeypatch.setattr(page.monthly_orders_service, 'product_monthly_rows_for', monthly)
    try:
        page.external_distributor_filter_id = 'warehouse'
        page.orders_comparison_year.setCurrentIndex(page.orders_comparison_year.findData(2024))
        page._current_entradas_articulo_id = 'p'
        page._reload_orders_comparison('p')
        assert calls[-1] == dict(articulo_id='p', almacen_id='warehouse', date_from=date(2023, 1, 1), date_to=date(2024, 12, 31))
        assert page.orders_view_buttons.button(1).text() == 'Detalle anual'
        for button in page.orders_view_buttons.buttons():
            assert not button.icon().isNull()
            assert button.height() == 30
        assert page.orders_views.currentIndex() == 0
        assert page.orders_views.widget(0).isAncestorOf(page.pedidos_table)
        page.orders_view_buttons.button(1).click()
        assert page.orders_views.currentIndex() == 1
        current, previous = page.orders_comparison_tables
        assert current.columnCount() == previous.columnCount() == 12
        assert current.rowCount() == previous.rowCount() == 1
        tabs = {page.detail_tabs.tabText(i): page.detail_tabs.widget(i) for i in range(page.detail_tabs.count())}
        assert tabs['Pedidos'].isAncestorOf(current)
        assert 'Mensual' not in tabs
        assert not hasattr(page, 'monthly_orders_table')
        assert page.pedidos_reset_btn.height() == page.pedidos_date_from.height() == 32
        assert not page.pedidos_reset_btn.icon().isNull()
        assert current.item(0, 0).font().bold()
        assert not current.item(0, 1).font().bold()
        assert current.item(0, 0).background() != current.item(0, 1).background()
        assert current.item(0, 0).background() == current.item(0, 2).background()
        assert current.item(0, 0).text() == '12.50'
        assert current.item(0, 11).text() == '9.00'
        assert current.item(0, 1).text() == '0.00'
        assert previous.item(0, 1).text() == '100.00'
        assert '21.50 uds' in page.orders_comparison_titles[0].text()
        assert '100.00 uds' in page.orders_comparison_titles[1].text()
        assert current.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        original_date = page.pedidos_date_from.date()
        page.orders_comparison_year.setCurrentIndex(page.orders_comparison_year.findData(2025))
        assert calls[-1]['date_to'] == date(2025, 12, 31)
        assert previous.item(0, 0).text() == '12.50'
        assert page.pedidos_date_from.date() == original_date
        page._reload_orders_comparison('other')
        assert all(current.item(0, month).text() == '0.00' for month in range(12))
        page._reload_pedidos_table('')
        assert current.item(0, 0).text() == '—'
        assert 'Selecciona' in page.orders_comparison_titles[0].text()
    finally:
        page.close()
