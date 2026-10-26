from datetime import date
from types import SimpleNamespace
import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.ui.widgets.ingredients_page import IngredientsIreksPage
from app.services.order_query_service import OrderQueryService, WarehouseFilterOption


@pytest.fixture(autouse=True)
def recipient_options(monkeypatch):
    monkeypatch.setattr(OrderQueryService, 'warehouse_filter_options', lambda self: [
        WarehouseFilterOption('Todos', ''),
        WarehouseFilterOption('CADELSA LZA (Cliente directo)', 'excluded'),
        WarehouseFilterOption('CADELSA [LANZAROTE-FUERTEVENTURA] (Distribuidor)', 'cadelsa'),
        WarehouseFilterOption('IGSA (Distribuidor)', 'igsa'),
        WarehouseFilterOption('Panadería Hermanos Rodríguez (Cliente directo)', 'hermanos'),
        WarehouseFilterOption('Panadería y Dulceria Backer Las Arenas Sin Glúten (Cliente directo)', 'arenas'),
    ])


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
        assert calls[-1] == dict(articulo_id='p', almacen_id='igsa', date_from=date(2023, 1, 1), date_to=date(2024, 12, 31))
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


def test_recipient_filters_orders_without_changing_dates(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(IngredientsIreksPage, 'reload', lambda self: None)
    page = IngredientsIreksPage()
    calls = []
    monkeypatch.setattr(page.monthly_orders_service, 'product_monthly_rows_for',
                        lambda **kwargs: calls.append(kwargs) or [])
    monkeypatch.setattr(OrderQueryService, 'list_raw_orders', lambda self: [
        SimpleNamespace(pedido_id=name, almacen_id=name)
        for name in ('igsa', 'cadelsa', 'hermanos', 'arenas')
    ])
    year = date.today().year
    rows = [SimpleNamespace(pedido_id=name, pedido_item_fecha=date(year, 9, 7),
                            pedido_numero=name, articulo_cantidad=quantity)
            for name, quantity in [('igsa', 5), ('cadelsa', 10), ('hermanos', 20), ('arenas', 60)]]
    rows.append(SimpleNamespace(pedido_id='igsa', pedido_item_fecha=date(year-1, 9, 7),
                                pedido_numero='old', articulo_cantidad=99))
    monkeypatch.setattr(page.ireks_service, 'pedido_items', lambda product: rows if product == '31118' else [])
    try:
        combo = page.pedidos_recipient
        assert [combo.itemText(i) for i in range(combo.count())] == [
            'IGSA', 'CADELSA [LANZAROTE-FUERTEVENTURA]', 'Panadería Hermanos Rodríguez',
            'Sin Gluten «Las Arenas»', 'Todos',
        ]
        page._current_entradas_articulo_id = '31118'
        page._reload_pedidos_table('31118')
        assert page.pedidos_table.rowCount() == 1
        assert page.pedidos_table.item(0, 3).text() == '5.00'
        original_dates = (page.pedidos_date_from.date(), page.pedidos_date_to.date())
        for identity, quantity in [('cadelsa', '10.00'), ('hermanos', '20.00'), ('arenas', '60.00')]:
            combo.setCurrentIndex(combo.findData(identity))
            assert page.pedidos_table.rowCount() == 1
            assert page.pedidos_table.item(0, 3).text() == quantity
            assert calls[-1]['almacen_id'] == identity
        combo.setCurrentIndex(combo.findData(''))
        assert page.pedidos_table.rowCount() == 4
        assert calls[-1]['almacen_id'] == ''
        assert original_dates == (page.pedidos_date_from.date(), page.pedidos_date_to.date())
        page._current_entradas_articulo_id = 'other'
        page._reload_pedidos_table('other')
        assert page.pedidos_table.rowCount() == 0
        assert combo.currentText() == 'Todos'
    finally:
        page.close()
