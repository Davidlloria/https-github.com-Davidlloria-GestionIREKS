import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook
from sqlmodel import SQLModel, Session, create_engine, select

from app.models import AlmacenMovimiento, IngredienteIreks
from app.services.inventory_review_service import InventoryReviewService


def test_historical_review_preserves_zero_pending_expired_and_future(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'review.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(IngredienteIreks(articulo_id="p", articulo_referencia="00100", articulo_envase_peso=5))
        for lot, quantity, day, warehouse in [('A', 10, date(2026, 5, 29), 'igsa'),
                                              ('A', -3, date(2026, 6, 1), 'igsa'),
                                              ('A', 40, date(2026, 5, 29), 'other'),
                                              ('B', 2, date(2026, 5, 1), 'igsa'),
                                              ('C', 4, date(2026, 5, 1), 'igsa')]:
            session.add(AlmacenMovimiento(almacen_id=warehouse, articulo_id='p', cantidad=quantity,
                                          articulo_lote=lot, fecha_pedido=day))
        session.commit()
    book = Workbook()
    sheet = book.active
    sheet.title = 'INVENTARIO'
    sheet.append(['Título']); sheet.append([])
    sheet.append(['Almacén', 'Artículo', 'Descripción', 'Lote', 'Fecha cons.pref.', 'Stock', 'Envases',
                  'Conteo Envases', 'MUESTRAS', 'PROMOCION', 'VENTAS MAYO', '', 'DELTA', 'COMENTARIOS'])
    sheet.append([7, 100, 'Producto', 'A', date(2026, 4, 1), 999, 999, 0, 5, 6, 7, None, None, 'CADUCADO'])
    sheet.append([7, 100, 'Producto', 'B', None, 0, 0, None])
    path = tmp_path / 'inventory.xlsx'
    book.save(path)
    rows = InventoryReviewService(engine).compare(path, 'igsa', date(2026, 5, 29))
    a, b, c = rows
    assert (a['theoretical'], a['count'], a['delta'], a['kg']) == (10, 0, -10, -50)
    assert 'Caducado' in a['status']
    assert b['count'] is None and b['delta'] is None
    assert c['lot'] == 'C' and c['delta'] is None and 'No figura' in c['status']
    with Session(engine) as session:
        assert len(list(session.exec(select(AlmacenMovimiento)))) == 5
    sheet.append([7, '00100', 'Duplicado', 'A', None, 0, 0, 2])
    book.save(path)
    rows = InventoryReviewService(engine).compare(path, 'igsa', date(2026, 5, 29))
    assert rows[0]['delta'] is None and 'duplicados' in rows[0]['status']


def test_review_dialog_is_read_only_and_invalidates_old_results():
    from PySide6.QtWidgets import QApplication, QAbstractItemView
    from app.ui.widgets.inventory_review_dialog import InventoryReviewDialog
    app = QApplication.instance() or QApplication([])
    class Service:
        def compare(self, path, warehouse, cutoff):
            assert cutoff == date(2026, 5, 29)
            return [dict(row=4, code='P1', name='Producto', lot='A', expiry='', theoretical=5,
                         count=None, delta=None, kg=None, status='Pendiente', notes='')]
    dialog = InventoryReviewDialog('igsa', service=Service())
    dialog.path.setText('inventory.xlsx')
    dialog._compare()
    assert dialog.table.rowCount() == 1
    assert dialog.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert '1 pendientes' in dialog.summary.text()
    dialog.cutoff.setDate(dialog.cutoff.date().addDays(1))
    assert not dialog.rows and dialog.table.rowCount() == 0
    dialog.close()
