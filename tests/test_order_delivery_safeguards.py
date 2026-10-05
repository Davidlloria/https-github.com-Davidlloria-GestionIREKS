from datetime import date
import pytest
from sqlmodel import SQLModel, Session, create_engine, select
from app.models import Pedido, PedidoItem, Albaran, AlbaranItem, AlmacenMovimiento, PedidoRecepcionRevision, PedidoRecepcionReparto
from app.services import order_document_import_service as documents
from app.services import order_receipt_assignment_service as receipts
from app.services import order_query_service as queries


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'safeguards.db'}")
    SQLModel.metadata.create_all(engine)
    for module in (documents, receipts, queries):
        monkeypatch.setattr(module, 'engine', engine)
    with Session(engine) as session:
        session.add(Pedido(pedido_id='p', almacen_id='w', pedido_numero='2738', pedido_fecha=date(2026, 9, 29)))
        session.add(PedidoItem(pedido_id='p', articulo_id='x', articulo_cantidad=10))
        session.commit()
    return engine


def test_earlier_date_blocks_entire_import_before_writes(db):
    service = documents.OrderDocumentImportService()
    rows = [dict(albaran_numero='A', albaran_fecha='2026-09-30', articulo_codigo='X', articulo_cantidad=5),
            dict(albaran_numero='A', albaran_fecha='2026-09-28', articulo_codigo='X', articulo_cantidad=5)]
    with pytest.raises(ValueError, match='28/09/2026'):
        service.import_albaran('p', dict(albaran_numero='A'), rows)
    with Session(db) as session:
        assert list(session.exec(select(Albaran))) == []
        assert list(session.exec(select(AlbaranItem))) == []
        assert list(session.exec(select(AlmacenMovimiento))) == []
        assert session.get(Pedido, 'p').pedido_albaran_numero == ''


def test_reevaluate_after_date_change_preserves_confirmed_and_is_idempotent(db):
    with Session(db) as session:
        session.add(Albaran(albaran_id='a', pedido_id='p', almacen_id='w', albaran_fecha=date(2026, 9, 28)))
        item = AlbaranItem(item_id='i', albaran_id='a', pedido_id='p', articulo_id='x', articulo_cantidad=10.0, albaran_fecha=date(2026, 9, 28))
        session.add(item)
        session.flush()
        receipts.track_receipt(session, item)
        session.commit()
    service = receipts.ReceiptAssignmentService()
    service.reevaluate('p')
    assert service.pending_count(pedido_id='p') == 1
    with Session(db) as session:
        order = session.get(Pedido, 'p')
        order.pedido_fecha = date(2026, 9, 28)
        session.add(order)
        session.commit()
    message = service.reevaluate('p')
    assert 'Unidades asignadas: 10' in message
    assert service.pending_count(pedido_id='p') == 0
    with Session(db) as session:
        revision = session.get(PedidoRecepcionRevision, 'i')
        version = revision.version
        revision.estado = 'confirmado'
        session.add(revision)
        session.commit()
    service.reevaluate('p')
    with Session(db) as session:
        assert session.get(PedidoRecepcionRevision, 'i').estado == 'confirmado'
        assert session.get(PedidoRecepcionRevision, 'i').version == version
        assert len(list(session.exec(select(PedidoRecepcionReparto)))) == 1
        assert list(session.exec(select(AlmacenMovimiento))) == []


def test_preflight_reports_unknown_codes_without_writes(db):
    missing = documents.OrderDocumentImportService().preflight_albaran('p', {}, [
        dict(albaran_fecha='2026-09-29', articulo_codigo='UNKNOWN')])
    assert missing == ['UNKNOWN']
    with Session(db) as session:
        assert list(session.exec(select(Albaran))) == []


def test_date_guard_also_runs_before_duplicate_repair(db, monkeypatch):
    service = documents.OrderDocumentImportService()
    def forbidden(**kwargs):
        pytest.fail('Duplicate repair must not run before date validation')
    monkeypatch.setattr(service.import_flow_service, 'resolve_albaran_gate', forbidden)
    with pytest.raises(ValueError, match='Importación detenida'):
        service.import_albaran('p', dict(albaran_numero='A', albaran_fecha='2026-09-28'), [])


def test_preview_stops_before_confirmation_on_invalid_date(monkeypatch):
    from types import SimpleNamespace
    from app.ui.widgets import orders_page as ui
    messages = []
    def check(*args):
        raise ValueError('Albarán anterior al pedido')
    page = SimpleNamespace(_selected_row=lambda: SimpleNamespace(pedido_id='p'),
        order_document_import_service=SimpleNamespace(preflight_albaran=check))
    monkeypatch.setattr(ui.QMessageBox, 'warning', lambda *args: messages.append(args[2]))
    monkeypatch.setattr(ui, 'AlbaranPreviewDialog', lambda **kwargs: pytest.fail('Preview should not open'))
    assert ui.OrdersPage._confirm_albaran_preview(page, {}, []) is False
    assert messages == ['Albarán anterior al pedido']
