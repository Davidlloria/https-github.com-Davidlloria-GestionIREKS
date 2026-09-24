import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlmodel import Session, SQLModel, create_engine
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from app.models import VentaMensualRaw
from app.services.igsa_sale_details_service import IgsaSaleDetailsService
from app.ui.widgets.igsa_sale_details_dialog import IgsaSaleDetailsDialog


def test_detail_preserves_lots_and_filters_month_year_source(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'details.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for ident, source, period, kilos, sc, euros, payload in [
            ('paid', 'igsa', '2026-08', 10, 0, 30, {'cantidad': 2, 'envase_peso': 5, 'lote': '001', 'tipo': 'venta', 'precio_kg_snapshot': 3}),
            ('pending', 'igsa', '2026-08', 5, 0, 0, {'cantidad': 1, 'lote': '002', 'tipo': 'venta'}),
            ('sample', 'igsa', '2026-08', 0, 5, 0, {'cantidad': 1, 'lote': '003', 'tipo': 'muestras'}),
            ('prev', 'igsa_pdf', '2025-08', 4, 0, 8, {'cantidad': 1, 'lote': '004'}),
            ('july', 'igsa', '2026-07', 1, 0, 2, {}),
            ('central', 'ireks', '2026-08', 99, 0, 99, {}),
            ('old', 'igsa', '2024-08', 99, 0, 99, {}),
        ]:
            session.add(VentaMensualRaw(raw_id=ident, fuente=source, periodo=period, articulo_id='p', articulo_codigo_origen='P1', venta_kilos=kilos, venta_kilos_sc=sc, venta_euros=euros, payload_json=json.dumps(payload)))
        session.commit()
    service = IgsaSaleDetailsService(engine)
    rows = service.list_lines(2026, 8)
    assert len(rows) == 4
    assert {r['lote'] for r in rows} == {'001', '002', '003', '004'}
    assert sum(r['euros'] for r in rows) == 38
    assert len([r for r in rows if r['incidencias']]) == 1
    assert next(r for r in rows if r['lote'] == '001')['precio'] == 3
    assert next(r for r in rows if r['lote'] == '003')['tipo'] == 'Muestra'
    assert len(service.list_lines(2026, 8, True)) == 5
    assert len(service.list_lines(2026, 7)) == 1
    engine.dispose()


def test_detail_and_incident_dialogs_show_real_line_data():
    app = QApplication.instance() or QApplication([])
    rows = [dict(periodo='2026-08', tipo='Venta', cantidad=2, peso=5, kilos=10, precio=None, euros=0,
                 lote='00042', caducidad='', observaciones='Nota original', incidencias=['Importe pendiente'])]
    dialog = IgsaSaleDetailsDialog('P1', 'Producto', rows)
    assert dialog.table.item(0, 7).text() == '00042'
    assert dialog.table.item(0, 5).text() == '—'
    dialog.table.selectRow(0)
    app.processEvents()
    assert 'Nota original' in dialog.findChild(QPlainTextEdit).toPlainText()
    assert dialog.table.item(0, 0).foreground().color().name() == '#854d0e'
    explanation = IgsaSaleDetailsDialog('P1', 'Producto', rows, incidents_only=True)
    assert '00042' in explanation.findChild(QPlainTextEdit).toPlainText()
    assert 'Importe pendiente' in explanation.findChild(QPlainTextEdit).toPlainText()
    dialog.close()
    explanation.close()
