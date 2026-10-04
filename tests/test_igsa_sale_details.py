import json
import os
from pathlib import Path

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


def test_incident_selection_and_widths_with_application_theme():
    from PySide6.QtGui import QFont, QFontDatabase
    app = QApplication.instance() or QApplication([])
    previous_style = app.styleSheet()
    previous_font = app.font()
    font_path = Path('C:/Windows/Fonts/segoeui.ttf')
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        app.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 10))
    app.setStyleSheet((Path(__file__).resolve().parents[1] / 'assets/styles.qss').read_text(encoding='utf-8'))
    rows = [dict(periodo='2026-08', tipo='Promoción', cantidad=1200, peso=12.5, kilos=15000,
                 precio=15.25, euros=228750, lote='000123456789', caducidad='2027-08-31',
                 observaciones='', incidencias=['Importe pendiente'])]
    dialog = IgsaSaleDetailsDialog('P1', 'Producto con incidencia', rows)
    try:
        dialog.show()
        dialog.table.selectRow(0)
        app.processEvents()
        table = dialog.table
        assert table.columnWidth(7) == 120
        for column in range(9):
            assert table.columnWidth(column) >= table.fontMetrics().horizontalAdvance(table.horizontalHeaderItem(column).text()) + 16
        assert table.horizontalScrollBar().maximum() == 0
        rect = table.visualItemRect(table.item(0, 0))
        shot = table.viewport().grab().toImage()
        assert shot.pixelColor(rect.left() + 2, rect.center().y()).name() == '#fde68a'
        dialog.resize(1050, 620)
        app.processEvents()
        assert table.horizontalScrollBar().maximum() == 0
    finally:
        dialog.close()
        app.setStyleSheet(previous_style)
        app.setFont(previous_font)


def test_manual_correction_audits_validates_and_rejects_stale_data(tmp_path):
    import pytest
    from app.models import IngredienteIreks
    engine = create_engine(f"sqlite:///{tmp_path / 'corrections.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(IngredienteIreks(articulo_id='p', articulo_referencia='P1', articulo_descripcion='Pan'))
        session.add(VentaMensualRaw(raw_id='sale', fuente='igsa', periodo='2026-08', articulo_id='p',
            articulo_codigo_origen='P1', venta_kilos=10, venta_euros=0,
            payload_json=json.dumps(dict(cantidad=2, envase_peso=5, observaciones='No coincide', lote='001'))))
        session.commit()
    service = IgsaSaleDetailsService(engine)
    row = service.list_lines(2026, 8)[0]
    values = dict(articulo_id='p', tipo='venta', cantidad=3, peso=5, euros=45)
    with pytest.raises(ValueError):
        service.correct('sale', row['snapshot'], reason='', values=values)
    with pytest.raises(ValueError):
        service.correct('sale', row['snapshot'], reason='Error', values={**values, 'peso': 0})
    assert service.history('sale') == []
    service.correct('sale', row['snapshot'], reason='Verificado con documento', values=values, resolved=True)
    updated = service.list_lines(2026, 8)[0]
    assert (updated['kilos'], updated['euros'], updated['precio']) == (15, 45, 3)
    assert updated['incidencias'] == []
    assert updated['observaciones'] == 'No coincide'
    assert updated['lote'] == '001'
    history = service.history('sale')
    assert len(history) == 1
    assert json.loads(history[0]['anterior'])['venta_kilos'] == 10
    assert json.loads(history[0]['posterior'])['venta_kilos'] == 15
    with pytest.raises(ValueError, match='ha cambiado'):
        service.correct('sale', row['snapshot'], reason='Edición obsoleta', values=values)
    assert len(service.history('sale')) == 1
    service.correct('sale', updated['snapshot'], reason='Reabrir revisión', resolved=False)
    assert service.list_lines(2026, 8)[0]['incidencias']
    with Session(engine) as session:
        session.delete(session.get(VentaMensualRaw, 'sale'))
        session.commit()
    assert len(service.history('sale')) == 2


def test_comparison_uses_selected_party_month_and_separate_kg(tmp_path):
    from app.models import Cliente, IngredienteIreks
    engine = create_engine(f"sqlite:///{tmp_path / 'comparison.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Cliente(cliente_id='igsa', cliente_codigo=1, cliente_nombre_comercial='IGSA', cliente_tipo='distribuidor'))
        session.add(Cliente(cliente_id='other', cliente_codigo=2, cliente_nombre_comercial='Otro', cliente_tipo='distribuidor'))
        session.add(IngredienteIreks(articulo_id='p', articulo_referencia='P1', articulo_descripcion='Pan'))
        for ident, source, party, period, kg, sc in [
            ('a', 'igsa', 'igsa', '2026-08', 100, 5),
            ('b', 'ireks', 'igsa', '2026-08', 90, 5),
            ('c', 'ireks', 'other', '2026-08', 999, 999),
            ('d', 'igsa', 'igsa', '2025-08', 8, 0),
            ('e', 'ireks', 'igsa', '2026-07', 12, 0),
        ]:
            session.add(VentaMensualRaw(raw_id=ident, fuente=source, cliente_id=party, periodo=period,
                articulo_id='p', articulo_codigo_origen='P1', venta_kilos=kg, venta_kilos_sc=sc))
        session.commit()
    service = IgsaSaleDetailsService(engine)
    assert service.compare(2026, 8, cliente_id='') == []
    rows = service.compare(2026, 8, cliente_id='igsa')
    current = [r for r in rows if r['periodo'] == '2026-08']
    assert current[0]['diferencia'] == 10
    assert current[0]['estado'] == 'Diferencia'
    assert current[1]['estado'] == 'Coincide'
    previous = [r for r in rows if r['periodo'] == '2025-08']
    assert previous[0]['ireks'] is None
    assert previous[0]['estado'] == 'Sin datos para comparar'
    july = service.compare(2026, 7, cliente_id='igsa')
    assert july[0]['igsa'] is None
    assert july[0]['ireks'] == 12


def test_correction_dialog_requires_reason_and_saves_review():
    from types import SimpleNamespace
    from PySide6.QtWidgets import QDialogButtonBox
    from app.ui.widgets.igsa_sale_details_dialog import IgsaCorrectionDialog
    app = QApplication.instance() or QApplication([])
    calls = []
    def correct(*args, **kwargs):
        if not kwargs['reason']:
            raise ValueError('Motivo obligatorio')
        calls.append(kwargs)
    row = dict(raw_id='r', snapshot={}, articulo_id='p', tipo='Venta', cantidad=2, peso=5, euros=30)
    dialog = IgsaCorrectionDialog(row, SimpleNamespace(products=lambda: [], correct=correct))
    buttons = dialog.findChild(QDialogButtonBox)
    buttons.button(QDialogButtonBox.StandardButton.Save).click()
    assert not calls
    assert dialog.error.text() == 'Motivo obligatorio'
    dialog.reason.setText('Documento contrastado')
    dialog.resolved.setChecked(True)
    buttons.button(QDialogButtonBox.StandardButton.Save).click()
    assert calls[0]['values'] is None
    assert calls[0]['resolved'] is True
    assert dialog.result() == dialog.DialogCode.Accepted
