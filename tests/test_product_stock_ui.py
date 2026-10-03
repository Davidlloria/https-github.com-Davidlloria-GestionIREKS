from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from sqlmodel import SQLModel, Session, create_engine

from app.models import AlmacenMovimiento, AlmacenCatalogo, IngredienteIreks, InventarioCabecera
from app.services import ingredient_ireks_service as service_module
from app.services.ingredient_ireks_service import IngredientIreksService
from app.ui.widgets.ingredients_page import IngredientsIreksPage
from app.ui.widgets.warehouse_page import _compute_current_stock_rows


def test_stock_context_uses_latest_approved_inventory_and_does_not_write(monkeypatch):
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(AlmacenCatalogo(almacen_id='a', almacen_nombre='Central'))
        for identity, day, status in [('old', 1, 'aprobado'), ('new', 2, 'aprobado'), ('draft', 3, 'borrador')]:
            session.add(InventarioCabecera(inventario_id=identity, almacen_id='a', fecha=date(2024, 1, day), estado=status))
        session.commit()
    monkeypatch.setattr(service_module, 'engine', engine)
    with engine.connect() as connection:
        connection.exec_driver_sql('PRAGMA query_only = ON')
    names, inventories = IngredientIreksService().stock_context()
    assert names['a'] == 'Central'
    assert inventories == {'a': date(2024, 1, 2)}
    engine.dispose()


def test_product_stock_matches_warehouse_and_dates_only_filter_history(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(IngredientsIreksPage, 'reload', lambda self: None)
    moves = [
        AlmacenMovimiento(articulo_id='p', almacen_id='a', articulo_lote='L', cantidad=100, fecha_pedido=date(2023, 12, 1)),
        AlmacenMovimiento(articulo_id='p', almacen_id='a', articulo_lote='L', cantidad=-20, fecha_pedido=date(2024, 1, 1), pedido_albaran_numero='INV-AJUSTE|CONT:X'),
        AlmacenMovimiento(articulo_id='p', almacen_id='a', articulo_lote='L', cantidad=-5, fecha_pedido=date(2024, 2, 1)),
        AlmacenMovimiento(articulo_id='p', almacen_id='b', articulo_lote='L', cantidad=7, fecha_pedido=date(2024, 2, 1)),
    ]
    item = IngredienteIreks(articulo_id='p', almacen_id='a', articulo_envase_peso_total=10)
    page = IngredientsIreksPage()
    try:
        monkeypatch.setattr(page.ireks_service, 'movement_payload', lambda _: (moves, [item]))
        monkeypatch.setattr(page.ireks_service, 'stock_context', lambda: ({'a': 'Central', 'b': 'Norte'}, {'a': date(2024, 1, 1)}))
        page.stock_date_from.setDate(QDate(2024, 1, 1))
        page.stock_date_to.setDate(QDate(2024, 12, 31))
        page._current_entradas_articulo_id = 'p'
        page._reload_stock_table('p')
        assert page.stock_current_table.item(0, 2).text() == '75.00'
        expected = sum(row['cantidad'] for row in _compute_current_stock_rows(moves[:3]))
        assert float(page.stock_current_table.item(0, 2).text()) == expected
        assert page.stock_current_table.item(0, 3).text() == '750.00'
        assert page.stock_table.rowCount() == 2
        assert page.stock_table.item(0, 1).text() == 'Ajuste'
        assert page.stock_totals_table.item(0, 4).text() == '-25.00'
        assert '01/01/2024' in page.stock_inventory_label.text()
        page.stock_date_from.setDate(QDate(2025, 1, 1))
        page.stock_date_to.setDate(QDate(2025, 12, 31))
        assert page.stock_table.rowCount() == 0
        assert page.stock_current_table.item(0, 2).text() == '75.00'
        page.stock_warehouse_filter.setCurrentIndex(page.stock_warehouse_filter.findData('b'))
        assert page.stock_current_table.item(0, 2).text() == '7.00'
        assert 'Sin inventario aprobado' in page.stock_inventory_label.text()
        page._reload_stock_table('')
        assert page.stock_current_table.rowCount() == 0
        assert page.stock_warehouse_filter.count() == 0
        monkeypatch.setattr(page.ireks_service, 'movement_payload', lambda _: ([], []))
        page._reload_stock_table('empty')
        assert 'Sin almacén ni movimientos' in page.stock_current_label.text()
        assert page.stock_current_table.rowCount() == 0
        assert page.stock_table.rowCount() == 0
    finally:
        page.close()
