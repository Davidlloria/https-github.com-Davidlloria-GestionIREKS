from datetime import date

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (Albaran, AlbaranItem, AlmacenMovimiento, Factura, FacturaItem,
                        IngredienteIreks, Pedido, PedidoItem, PedidoPendiente, PedidoRecepcionRevision)
from app.services import order_document_import_service as module


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(module, "engine", engine)
    with Session(engine) as session:
        session.add(Pedido(pedido_id="p1", almacen_id="alm", pedido_numero="P1", pedido_fecha=date(2026, 10, 1)))
        session.add(IngredienteIreks(articulo_id="a1", articulo_referencia="8102", articulo_envase_peso_total=12.5))
        session.add(PedidoItem(pedido_id="p1", articulo_id="a1", articulo_cantidad=20))
        session.commit()
    yield engine
    engine.dispose()


def invoices():
    rows = []
    for number, lot, qty in (("60062", "L1", 2), ("60063", "L2", 3)):
        metadata = dict(factura_numero=number, factura_fecha="13/10/2026", albaran_numero="2026090131",
                        total_factura=str(qty * 10), importe_neto=str(qty * 10), total_kilos=str(qty * 12.5))
        rows.append(dict(metadata, articulo_codigo="8102", articulo_cantidad=str(qty), articulo_envase="12,50",
                         articulo_kilos=str(qty * 12.5), articulo_lote=lot, articulo_caducidad="09/02/2028",
                         precio_unitario="1", dto_pct="20", total_linea=str(qty * 10), _factura_header=metadata))
    return {"factura_numero": "60062, 60063"}, rows


def counts(engine):
    with Session(engine) as session:
        return tuple(len(session.exec(select(model)).all()) for model in
                     (Factura, FacturaItem, Albaran, AlbaranItem, AlmacenMovimiento, PedidoRecepcionRevision))


def test_two_invoices_create_one_complete_delivery_and_repeat_is_noop(database):
    service = module.OrderDocumentImportService()
    header, rows = invoices()
    plan = service.preview_facturas_with_albaranes("p1", header, rows)
    assert "2 líneas" in plan and "2026-10-13" in plan
    assert counts(database) == (0, 0, 0, 0, 0, 0)
    result = service.import_facturas_with_albaranes("p1", header, rows)
    assert result.imported == 2 and not result.errors
    assert counts(database) == (2, 2, 1, 2, 2, 2)
    with Session(database) as session:
        assert session.exec(select(Albaran)).one().albaran_fecha == date(2026, 10, 13)
        items = session.exec(select(AlbaranItem)).all()
        assert {(item.articulo_lote, item.articulo_cantidad) for item in items} == {("L1", 2), ("L2", 3)}
        assert {invoice.total_factura for invoice in session.exec(select(Factura))} == {20, 30}
        assert session.exec(select(PedidoPendiente)).one().cantidad_pendiente == 15
    result = service.import_facturas_with_albaranes("p1", header, rows)
    assert result.already_imported and result.imported == 0
    assert counts(database) == (2, 2, 1, 2, 2, 2)


def test_existing_delivery_is_preserved_including_receipt_decisions(database):
    with Session(database) as session:
        delivery = Albaran(pedido_id="p1", almacen_id="alm", albaran_numero="2026090131", albaran_fecha=date(2026, 10, 12))
        session.add(delivery)
        item = AlbaranItem(pedido_id="p1", albaran_id=delivery.albaran_id, articulo_codigo="8102",
                           articulo_id="a1", articulo_cantidad=99, cantidad_recibida_confirmada=7, articulo_lote="ORIGINAL")
        session.add(item)
        session.commit()
        item_id = item.item_id
    result = module.OrderDocumentImportService().import_facturas_with_albaranes("p1", *invoices())
    assert result.imported == 2
    assert counts(database) == (2, 2, 1, 1, 0, 0)
    with Session(database) as session:
        item = session.get(AlbaranItem, item_id)
        assert item.articulo_lote == "ORIGINAL" and item.cantidad_recibida_confirmada == 7
        assert session.exec(select(Albaran)).one().albaran_fecha == date(2026, 10, 12)


def test_existing_invoice_does_not_prevent_missing_delivery_completion(database):
    header, rows = invoices()
    service = module.OrderDocumentImportService()
    service.import_factura("p1", rows[0]["_factura_header"], rows[:1])
    result = service.import_facturas_with_albaranes("p1", header, rows)
    assert result.imported == 1
    assert counts(database) == (2, 2, 1, 2, 2, 2)


@pytest.mark.parametrize("stage", ["second_invoice", "after_pending"])
def test_failure_rolls_back_invoices_delivery_movements_and_pending(database, monkeypatch, stage):
    service = module.OrderDocumentImportService()
    if stage == "second_invoice":
        original = service.import_factura

        def fail(pedido_id, header, rows, **kwargs):
            if header["factura_numero"] == "60063":
                raise ValueError("fallo controlado")
            return original(pedido_id, header, rows, **kwargs)
        monkeypatch.setattr(service, "import_factura", fail)
    else:
        original = service.rebuild_order_pendientes

        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("fallo controlado")
        monkeypatch.setattr(service, "rebuild_order_pendientes", fail)
    with pytest.raises(ValueError, match="fallo controlado"):
        service.import_facturas_with_albaranes("p1", *invoices())
    assert counts(database) == (0, 0, 0, 0, 0, 0)
    with Session(database) as session:
        assert session.get(Pedido, "p1").pedido_albaran_numero == ""
        assert session.get(Pedido, "p1").pedido_factura_numero == ""
        assert not session.exec(select(PedidoPendiente)).all()


@pytest.mark.parametrize("field,value", [("articulo_codigo", "DESCONOCIDO"), ("articulo_lote", ""),
                                        ("articulo_caducidad", ""), ("articulo_cantidad", "0"),
                                        ("factura_fecha", "01/09/2026"), ("precio_unitario", "nan")])
def test_invalid_input_stops_without_partial_import(database, field, value):
    header, rows = invoices()
    rows[1][field] = value
    with pytest.raises(ValueError):
        module.OrderDocumentImportService().import_facturas_with_albaranes("p1", header, rows)
    assert counts(database) == (0, 0, 0, 0, 0, 0)


def test_same_warehouse_document_on_other_order_is_rejected(database):
    with Session(database) as session:
        session.add(Factura(pedido_id="other", almacen_id="alm", factura_numero="60063"))
        session.commit()
    with pytest.raises(ValueError, match="otro pedido"):
        module.OrderDocumentImportService().import_facturas_with_albaranes("p1", *invoices())
    assert counts(database) == (1, 0, 0, 0, 0, 0)


def test_zero_price_and_document_packaging_are_preserved(database):
    service = module.OrderDocumentImportService()
    header, rows = invoices()
    rows = rows[:1]
    rows[0].update(precio_unitario="0", total_linea="0", articulo_envase="1", articulo_kilos="2",
                   _precio_cero_explicito=True)
    rows[0]["_factura_header"].update(importe_neto="0", total_factura="0")
    enriched = service.enrich_factura_rows_from_tarifa(rows)
    assert enriched[0]["articulo_envase"] == "1,00" and enriched[0]["articulo_kilos"] == "2,00"
    service.import_facturas_with_albaranes("p1", header, enriched)
    with Session(database) as session:
        item = session.exec(select(FacturaItem)).one()
        assert item.precio_unitario == 0 and item.total_linea == 0


def test_repeated_pdf_line_is_caught_by_invoice_net_total(database):
    header, rows = invoices()
    rows.append(dict(rows[0]))
    with pytest.raises(ValueError, match="importe neto"):
        module.OrderDocumentImportService().import_facturas_with_albaranes("p1", header, rows)
    assert counts(database) == (0, 0, 0, 0, 0, 0)


def test_duplicate_delivery_headers_are_not_silently_selected(database):
    with Session(database) as session:
        for _ in range(2):
            session.add(Albaran(pedido_id="p1", almacen_id="alm", albaran_numero="2026090131"))
        session.commit()
    with pytest.raises(ValueError, match="ambigua"):
        module.OrderDocumentImportService().import_facturas_with_albaranes("p1", *invoices())
    assert counts(database) == (0, 0, 2, 0, 0, 0)
